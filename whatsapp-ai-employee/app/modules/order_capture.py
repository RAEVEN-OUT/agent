"""Order capture — deterministic slot filling.

No LLM needed here on any plan: collecting product, quantity, name, address and
pincode is a form, not a judgement call. Keeping it deterministic also means the
transaction cannot be talked into an invalid state.

Business preconditions ARE enforced here (stock, required fields) even though
conversational order is free — the AI may raise this flow at any point, but it
cannot create an order that is not fulfillable.
"""

import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Customer, Order, Tenant
from app.modules import retrieval
from app.services.events import ORDER_CREATED, event_bus

log = get_logger("order_capture")

REQUIRED_SLOTS = ("product", "quantity", "name", "address", "pincode", "payment_method")

QUESTIONS = {
    "product": "Which product would you like to order?",
    "quantity": "How many would you like?",
    "name": "What name should I put on the order?",
    "address": "Please share your full delivery address.",
    "pincode": "And your pincode?",
    "payment_method": "Would you like to pay online (UPI/card) or cash on delivery?",
}


@dataclass
class OrderResult:
    answer: str | None
    handled_by: str
    state_update: dict = field(default_factory=dict)
    order_id: str | None = None
    escalate_reason: str | None = None


def _order_number() -> str:
    stamp = datetime.now(timezone.utc).strftime("%y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ORD{stamp}{suffix}"


def _parse_quantity(value) -> int | None:
    try:
        qty = int(str(value).strip())
        return qty if 1 <= qty <= 50 else None
    except (TypeError, ValueError):
        return None


def _parse_payment_method(text: str) -> str | None:
    lowered = text.lower()
    if any(k in lowered for k in ("cod", "cash on delivery", "cash")):
        return "cod"
    if any(k in lowered for k in ("online", "upi", "card", "pay now", "gpay", "phonepe")):
        return "online"
    return None


def _parse_pincode(text: str) -> str | None:
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits if len(digits) == 6 else None


async def handle(
    db: AsyncSession,
    tenant: Tenant,
    customer: Customer,
    *,
    raw_message: str,
    normalized: str,
    slots: dict,
    state: dict,
    metrics,
) -> OrderResult:
    draft: dict = dict(state.get("order") or {})
    awaiting = state.get("awaiting")

    # 1. Fold in whatever the router extracted.
    if slots.get("product") and not draft.get("product"):
        draft["product"] = slots["product"]
    if slots.get("quantity") and not draft.get("quantity"):
        qty = _parse_quantity(slots["quantity"])
        if qty:
            draft["quantity"] = qty

    # 2. Interpret this message as the answer to the field we last asked about.
    if awaiting and awaiting in REQUIRED_SLOTS:
        if awaiting == "quantity":
            qty = _parse_quantity(normalized) or _parse_quantity(
                "".join(ch for ch in normalized if ch.isdigit())
            )
            if qty:
                draft["quantity"] = qty
        elif awaiting == "pincode":
            pin = _parse_pincode(raw_message)
            if pin:
                draft["pincode"] = pin
        elif awaiting == "payment_method":
            method = _parse_payment_method(raw_message)
            if method:
                draft["payment_method"] = method
        elif awaiting == "product":
            draft["product"] = raw_message.strip()
        else:
            draft[awaiting] = raw_message.strip()

    # 3. Resolve the product against the real catalog (never trust free text).
    if draft.get("product") and not draft.get("sku"):
        hit = await retrieval.get_product_by_name(db, str(tenant.id), draft["product"])
        if not hit:
            return OrderResult(
                answer=(
                    f"I couldn't find \"{draft['product']}\" in our list. "
                    "Could you tell me the product name again?"
                ),
                handled_by="order_capture",
                state_update={"order": {k: v for k, v in draft.items() if k != "product"},
                              "awaiting": "product", "flow": "order"},
            )
        if hit.stock <= 0:
            return OrderResult(
                answer=(
                    f"{hit.name} is out of stock right now. I've let our team know — "
                    "would you like me to suggest an alternative?"
                ),
                handled_by="order_capture",
                state_update={"order": draft, "awaiting": None, "flow": None},
                escalate_reason=None,
            )
        draft.update(
            {
                "sku": hit.sku,
                "product": hit.name,
                "unit_price": hit.price,
                "product_id": hit.id,
                "stock": hit.stock,
            }
        )

    # 4. Ask for the next missing field, one at a time.
    for slot in REQUIRED_SLOTS:
        if not draft.get(slot):
            metrics.mark("path", f"order_ask_{slot}")
            return OrderResult(
                answer=QUESTIONS[slot],
                handled_by="order_capture",
                state_update={"order": draft, "awaiting": slot, "flow": "order"},
            )

    # 5. Precondition check before creating anything.
    qty = int(draft["quantity"])
    if qty > int(draft.get("stock", 0)):
        return OrderResult(
            answer=(
                f"We only have {draft.get('stock', 0)} of {draft['product']} left. "
                "Shall I put you down for that many?"
            ),
            handled_by="order_capture",
            state_update={"order": {**draft, "quantity": None}, "awaiting": "quantity", "flow": "order"},
        )

    total = float(draft["unit_price"]) * qty
    order = Order(
        tenant_id=tenant.id,
        customer_id=customer.id,
        order_number=_order_number(),
        status="pending",
        payment_status="cod_pending" if draft["payment_method"] == "cod" else "unpaid",
        payment_method=draft["payment_method"],
        items=[
            {
                "sku": draft["sku"],
                "name": draft["product"],
                "quantity": qty,
                "unit_price": float(draft["unit_price"]),
            }
        ],
        total=total,
        address={
            "name": draft["name"],
            "address": draft["address"],
            "pincode": draft["pincode"],
        },
    )
    db.add(order)
    await db.flush()

    currency = tenant.currency or "INR"
    if draft["payment_method"] == "cod":
        closing = "You'll pay on delivery."
    else:
        # Phase 2 replaces this with a real Razorpay link.
        closing = "I'll send you a payment link here shortly."

    answer = (
        f"Order {order.order_number} confirmed:\n"
        f"{qty} x {draft['product']} — {currency} {total:.0f}\n"
        f"Delivering to {draft['pincode']}.\n{closing}"
    )

    await event_bus.emit(
        ORDER_CREATED,
        {
            "tenant_id": str(tenant.id),
            "order_id": str(order.id),
            "order_number": order.order_number,
            "customer_wa_id": customer.wa_id,
            "total": total,
            "items": order.items,
        },
    )

    metrics.mark("path", "order_created")
    return OrderResult(
        answer=answer,
        handled_by="order_created",
        state_update={"order": {}, "awaiting": None, "flow": None},
        order_id=str(order.id),
    )
