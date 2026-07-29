from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, Order, Tenant

STATUS_TEXT = {
    "pending": "received and being prepared",
    "confirmed": "confirmed and being packed",
    "packed": "packed and awaiting dispatch",
    "shipped": "shipped and on its way",
    "delivered": "delivered",
    "cancelled": "cancelled",
}


@dataclass
class StatusResult:
    answer: str | None
    handled_by: str = "order_status"
    escalate_reason: str | None = None


async def handle(
    db: AsyncSession, tenant: Tenant, customer: Customer, *, metrics
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
                "a different number, tell me the order number and I'll check."
            )
        )

    latest = orders[0]
    human = STATUS_TEXT.get(latest.status, latest.status)
    currency = tenant.currency or "INR"

    lines = [
        f"Order {latest.order_number} is {human}.",
        f"Total: {currency} {float(latest.total):.0f}",
    ]
    if latest.payment_status == "unpaid":
        lines.append("Payment is still pending.")
    if len(orders) > 1:
        lines.append(f"(You have {len(orders)} recent orders — ask me about any of them.)")

    metrics.mark("path", "status_found")
    return StatusResult(answer="\n".join(lines))
