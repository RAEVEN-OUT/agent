from datetime import datetime, timezone

from fastapi import APIRouter, Header, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Conversation, Customer, Message, Tenant
from app.db.session import SessionLocal
from app.pipeline.orchestrator import process_message
from app.services.events import MESSAGE_RECEIVED, event_bus
from app.services.redis_service import redis_service
from app.services.whatsapp_service import whatsapp_service

log = get_logger("webhook")
router = APIRouter(tags=["webhook"])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
):
    """Meta calls this once when you register the callback URL."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        log.info({"event": "webhook_verified"})
        return Response(content=hub_challenge, media_type="text/plain")
    log.warning({"event": "webhook_verify_failed", "mode": hub_mode})
    return Response(content="forbidden", status_code=403)


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
):
    """Always ack with 200 quickly.

    Meta retries anything else for up to 7 days, which turns one bug into a
    flood. We validate, ack, and do the work inline but defensively.
    """
    raw = await request.body()

    if not whatsapp_service.verify_signature(raw, x_hub_signature_256):
        log.warning({"event": "bad_signature"})
        return Response(content="forbidden", status_code=403)

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return {"status": "ignored"}

    try:
        await _handle_payload(payload)
    except Exception as exc:  # noqa: BLE001
        log.error({"event": "webhook_handler_error", "error": str(exc)}, exc_info=True)

    return {"status": "ok"}


async def _handle_payload(payload: dict) -> None:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Delivery/read receipts — log only.
            if value.get("statuses"):
                for status in value["statuses"]:
                    log.info(
                        {
                            "event": "message_status",
                            "status": status.get("status"),
                            "wamid": status.get("id"),
                        }
                    )
                continue

            messages = value.get("messages") or []
            if not messages:
                continue

            phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
            contacts = value.get("contacts") or []
            profile_name = None
            if contacts:
                profile_name = (contacts[0].get("profile") or {}).get("name")

            for message in messages:
                await _handle_message(phone_number_id, message, profile_name)


def _extract_text(message: dict) -> tuple[str, str, str | None]:
    """Return (text, msg_type, media_id)."""
    msg_type = message.get("type", "text")

    if msg_type == "text":
        return (message.get("text") or {}).get("body", ""), "text", None
    if msg_type == "interactive":
        interactive = message.get("interactive") or {}
        for key in ("button_reply", "list_reply"):
            if key in interactive:
                return interactive[key].get("title", ""), "interactive", None
        return "", "interactive", None
    if msg_type == "button":
        return (message.get("button") or {}).get("text", ""), "button", None
    if msg_type in ("image", "video", "document", "audio", "sticker"):
        media = message.get(msg_type) or {}
        return media.get("caption", ""), msg_type, media.get("id")
    if msg_type == "order":
        # WhatsApp cart message — Phase 2 turns this straight into an Order.
        return "I would like to order the items in my cart", "order", None
    return "", msg_type, None


def _entry_context(message: dict) -> dict:
    """Extract where this customer came from.

    Messages that originate from an ad that clicks to WhatsApp (or a Facebook
    page CTA) carry a `referral` object. If the ad or post is product-specific,
    its identifiers tell us what the customer is asking about before they say a
    word — the highest-converting, zero-inference entry point there is.

    Parsed defensively: field names vary and Meta adds to them over time, so we
    take what is present and ignore the rest.
    """
    referral = message.get("referral") or {}
    if not referral:
        return {}

    context = {
        "source_type": referral.get("source_type"),
        "source_id": referral.get("source_id"),
        "source_url": referral.get("source_url"),
        "headline": referral.get("headline"),
        "ctwa_clid": referral.get("ctwa_clid"),
    }

    # Encode the SKU in the ad's headline/body or landing URL (e.g.
    # ...?sku=ARG-OIL-100) and it lands here as a resolved product.
    from app.pipeline.fast_intent import extract_sku

    haystack = " ".join(
        str(v) for v in (referral.get("headline"), referral.get("body"),
                         referral.get("source_url")) if v
    )
    sku = extract_sku(haystack)
    if sku:
        context["sku"] = sku

    return {k: v for k, v in context.items() if v}


async def _handle_message(
    phone_number_id: str | None, message: dict, profile_name: str | None
) -> None:
    wamid = message.get("id")
    wa_id = message.get("from")
    if not wamid or not wa_id or not phone_number_id:
        return

    # Idempotency: Meta redelivers webhooks; never process one twice.
    if not await redis_service.claim_message(wamid):
        log.info({"event": "duplicate_webhook_skipped", "wamid": wamid})
        return

    text, msg_type, media_id = _extract_text(message)

    async with SessionLocal() as db:
        tenant = await _resolve_tenant(db, phone_number_id)
        if not tenant:
            log.warning({"event": "unknown_tenant", "phone_number_id": phone_number_id})
            return

        if await redis_service.is_rate_limited(str(tenant.id), wa_id):
            log.warning({"event": "rate_limited", "wa_id": wa_id})
            return

        customer = await _get_or_create_customer(db, tenant, wa_id, profile_name)
        conversation = await _get_or_create_conversation(db, tenant, customer)

        db.add(
            Message(
                tenant_id=tenant.id,
                conversation_id=conversation.id,
                wamid=wamid,
                direction="in",
                msg_type=msg_type,
                body=text or None,
                media_id=media_id,
            )
        )

        now = datetime.now(timezone.utc)
        customer.last_inbound_at = now
        conversation.last_message_at = now
        await db.flush()

        await event_bus.emit(
            MESSAGE_RECEIVED,
            {
                "tenant_id": str(tenant.id),
                "customer_wa_id": wa_id,
                "text": text,
                "type": msg_type,
            },
        )

        outcome = await process_message(
            db,
            tenant,
            customer,
            conversation,
            raw_message=text,
            has_media=media_id is not None,
            entry_context=_entry_context(message),
        )

        log.info(
            {
                "event": "message_handled",
                "tenant": tenant.slug,
                "wa_id": wa_id,
                "plan": tenant.plan,
                **outcome.metrics.as_dict(),
            }
        )

        if outcome.silent or not outcome.reply:
            await db.commit()
            return

        # We are always inside the 24h service window here (the customer just
        # messaged us), so a free-form reply is allowed and free.
        sent_id = None
        try:
            response = await whatsapp_service.send_text(
                tenant.whatsapp_phone_number_id, wa_id, outcome.reply
            )
            sent_id = (response.get("messages") or [{}])[0].get("id")
        except Exception as exc:  # noqa: BLE001
            log.error({"event": "reply_send_failed", "error": str(exc)})

        db.add(
            Message(
                tenant_id=tenant.id,
                conversation_id=conversation.id,
                wamid=sent_id,
                direction="out",
                msg_type="text",
                body=outcome.reply,
                intent=outcome.intent,
                handled_by=outcome.handled_by,
                meta=outcome.metrics.as_dict(),
            )
        )
        await db.commit()


async def _resolve_tenant(db: AsyncSession, phone_number_id: str) -> Tenant | None:
    result = await db.execute(
        select(Tenant).where(
            Tenant.whatsapp_phone_number_id == phone_number_id,
            Tenant.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _get_or_create_customer(
    db: AsyncSession, tenant: Tenant, wa_id: str, profile_name: str | None
) -> Customer:
    result = await db.execute(
        select(Customer).where(Customer.tenant_id == tenant.id, Customer.wa_id == wa_id)
    )
    customer = result.scalar_one_or_none()
    if customer:
        if profile_name and not customer.name:
            customer.name = profile_name
        return customer

    customer = Customer(
        tenant_id=tenant.id,
        wa_id=wa_id,
        name=profile_name,
        # Messaging us first is inbound consent for this conversation; marketing
        # opt-in is captured separately before any campaign send.
        opted_in=False,
    )
    db.add(customer)
    await db.flush()
    return customer


async def _get_or_create_conversation(
    db: AsyncSession, tenant: Tenant, customer: Customer
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant.id,
            Conversation.customer_id == customer.id,
            Conversation.status != "closed",
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        return conversation

    conversation = Conversation(tenant_id=tenant.id, customer_id=customer.id, state={})
    db.add(conversation)
    await db.flush()
    return conversation
