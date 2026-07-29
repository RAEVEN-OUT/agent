"""Human handoff.

Required by WhatsApp policy: if you automate replies inside the 24h window you
must provide a clear escalation path. It is also our safety valve — adverse
reactions and medical questions never get an automated answer.
"""

from app.core.logging import get_logger
from app.db.models import Conversation, Escalation, Tenant
from app.pipeline.guardrails import HOLDING_MESSAGES
from app.services.events import ESCALATION_RAISED, event_bus
from app.services.whatsapp_service import whatsapp_service

log = get_logger("escalation")

# Reasons where the bot must stay silent afterwards until a human clears it.
LOCKING_REASONS = {"adverse_reaction", "medical", "complaint", "human_request"}


async def raise_escalation(
    db,
    tenant: Tenant,
    conversation: Conversation,
    *,
    reason: str,
    detail: str = "",
    customer_wa_id: str | None = None,
) -> str:
    record = Escalation(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        reason=reason,
        detail=detail[:2000],
    )
    db.add(record)

    if reason in LOCKING_REASONS:
        conversation.human_handoff = True
        conversation.status = "escalated"

    await db.flush()

    await event_bus.emit(
        ESCALATION_RAISED,
        {
            "tenant_id": str(tenant.id),
            "conversation_id": str(conversation.id),
            "reason": reason,
            "detail": detail[:500],
            "customer_wa_id": customer_wa_id,
        },
    )

    # Notify the owner in-channel if they've configured their number.
    owner = tenant.owner_wa_id
    if owner and reason in LOCKING_REASONS:
        try:
            await whatsapp_service.send_text(
                tenant.whatsapp_phone_number_id,
                owner,
                f"[{reason.replace('_', ' ').upper()}] "
                f"Customer {customer_wa_id or 'unknown'} needs you.\n"
                f"Message: {detail[:300]}",
            )
        except Exception as exc:  # noqa: BLE001  never let notification failure break the reply
            log.warning({"event": "owner_notify_failed", "error": str(exc)})

    log.info(
        {
            "event": "escalation_raised",
            "tenant": str(tenant.id),
            "reason": reason,
            "conversation": str(conversation.id),
        }
    )

    return HOLDING_MESSAGES.get(reason, HOLDING_MESSAGES["low_confidence"])
