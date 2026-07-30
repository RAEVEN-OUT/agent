"""Order status — answers the question that was actually asked.

Regression origin: three different questions ("what name is the order under",
"when can I expect delivery", "why didn't you ask delivery details") all received
the identical canned status line. Routing to the right module is not enough if
the module then ignores the question — that reads as a loop and is exactly what
"the AI never answers" means from the customer's side.

Everything needed is already on the order record. Basic renders a fuller
template; Pro composes a grounded reply from those same facts.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Customer, Order, Tenant
from app.pipeline.guardrails import CLAIMS_SYSTEM_RULES, sanitize_outbound
from app.services.llm_service import llm_service

log = get_logger("order_status")

STATUS_TEXT = {
    "pending": "received and being prepared",
    "confirmed": "confirmed and being packed",
    "packed": "packed and awaiting dispatch",
    "shipped": "shipped and on its way",
    "delivered": "delivered",
    "cancelled": "cancelled",
}

PAYMENT_TEXT = {
    "unpaid": "payment pending",
    "paid": "paid",
    "cod_pending": "cash on delivery",
    "failed": "payment failed",
}


@dataclass
class StatusResult:
    answer: str | None
    handled_by: str = "order_status"
    escalate_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def _order_facts(order: Order, tenant: Tenant, eta: str | None) -> str:
    """Every field a customer might ask about, as grounded text."""
    currency = tenant.currency or "INR"
    address = order.address or {}
    items = "; ".join(
        f"{i.get('quantity')} x {i.get('name')}"
        + (f" ({i.get('size')})" if i.get("size") else "")
        + f" at {currency} {i.get('unit_price')}"
        for i in (order.items or [])
    )
    lines = [
        f"Order number: {order.order_number}",
        f"Status: {STATUS_TEXT.get(order.status, order.status)}",
        f"Items: {items or 'n/a'}",
        f"Total: {currency} {float(order.total):.0f}",
        f"Payment: {PAYMENT_TEXT.get(order.payment_status, order.payment_status)}",
        f"Ordered on: {order.created_at:%d %b %Y}",
        f"Name on order: {address.get('name') or 'not recorded'}",
        f"Delivery address: {address.get('address') or 'not recorded'}",
        f"Pincode: {address.get('pincode') or 'not recorded'}",
    ]
    if eta:
        lines.append(f"Expected delivery: {eta}")
    return "\n".join(lines)


def _template(order: Order, tenant: Tenant, eta: str | None) -> str:
    currency = tenant.currency or "INR"
    address = order.address or {}
    parts = [
        f"Order {order.order_number} — {STATUS_TEXT.get(order.status, order.status)}.",
        f"Total: {currency} {float(order.total):.0f} "
        f"({PAYMENT_TEXT.get(order.payment_status, order.payment_status)})",
    ]
    if address.get("name"):
        parts.append(f"Name: {address['name']}")
    if address.get("pincode"):
        parts.append(f"Delivering to {address['pincode']}")
    if eta:
        parts.append(f"Expected by {eta}")
    return "\n".join(parts)


async def handle(
    db: AsyncSession,
    tenant: Tenant,
    customer: Customer,
    *,
    raw_message: str = "",
    metrics,
) -> StatusResult:
    result = await db.execute(
        select(Order)
        .where(Order.tenant_id == tenant.id, Order.customer_id == customer.id)
        .order_by(Order.created_at.desc())
        .limit(3)
    )
    orders = result.scalars().all()

    if not orders:
        metrics.mark("path", "status_none")
        return StatusResult(
            answer=(
                "I couldn't find an order under this number. If you ordered with "
                "a different number, send me the order number and I'll check."
            )
        )

    latest = orders[0]

    # Delivery estimate is computed, never invented by the model.
    from app.modules.order_capture import _delivery_estimate

    eta = None
    if latest.status not in ("delivered", "cancelled"):
        eta = _delivery_estimate(tenant, (latest.address or {}).get("pincode"))

    if not tenant.is_pro or not llm_service.available:
        metrics.mark("path", "status_template")
        return StatusResult(answer=_template(latest, tenant, eta))

    facts = _order_facts(latest, tenant, eta)
    if len(orders) > 1:
        facts += f"\nNote: this customer has {len(orders)} recent orders."

    system = (
        f"You are the assistant for {tenant.name} on WhatsApp, answering a "
        "question about an existing order.\n"
        "Answer ONLY the question asked, using ONLY the ORDER FACTS below.\n"
        "Do not dump every field — pick what answers the question.\n"
        "If the facts do not contain the answer, say you'll check with the team.\n"
        "Under 50 words. No greeting; you are mid-conversation.\n\n"
        + CLAIMS_SYSTEM_RULES
    )
    prompt = f"ORDER FACTS:\n{facts}\n\nCustomer question: {raw_message}"

    try:
        composed = await llm_service.generate(system, prompt, temperature=0.2)
    except Exception as exc:  # noqa: BLE001
        log.error({"event": "status_compose_failed", "error": str(exc)})
        metrics.mark("path", "status_template_degraded")
        return StatusResult(answer=_template(latest, tenant, eta))

    safe_text, violations = sanitize_outbound(composed.text)
    if violations:
        log.warning({"event": "claim_blocked", "module": "order_status"})

    if not safe_text:
        metrics.mark("path", "status_template_degraded")
        return StatusResult(answer=_template(latest, tenant, eta))

    metrics.mark("path", "status_composed")
    return StatusResult(
        answer=safe_text,
        handled_by="order_status_composed",
        input_tokens=composed.input_tokens,
        output_tokens=composed.output_tokens,
    )
