"""Sales stage tracking — "catches up, processes, proceeds to the next step".

This is the piece neither architecture had, and no amount of retrieval tuning
produces it. A retrieval bot answers questions and stops. A salesperson knows
*where the conversation is* and what the single next move should be.

The failure it fixes: the bot answering "Tea Tree Shampoo is INR 499" perfectly
and then waiting, when a salesperson would have said "...shall I add it for you?"
— and, after an order, still pitching products instead of confirming delivery.

Stage is *derived*, never stored, so it cannot drift out of sync with reality.
Every reply then carries exactly one forward action appropriate to the stage.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, Order, Tenant


class Stage(str, Enum):
    NEW = "new"                    # never spoken before
    BROWSING = "browsing"          # general questions, no product fixed
    INTERESTED = "interested"      # a specific product is on the table
    PROFILING = "profiling"        # consultation intake running
    CONFIGURING = "configuring"    # order slots being collected
    CONFIRMING = "confirming"      # summary shown, awaiting yes/no
    ORDERED = "ordered"            # order placed, not yet delivered
    POST_PURCHASE = "post_purchase"  # delivered — retention territory


# The one thing the bot should be driving toward at each stage.
NEXT_ACTION = {
    Stage.NEW: "greet briefly, then find out what they are looking for",
    Stage.BROWSING: "identify their need or concern so you can recommend something specific",
    Stage.INTERESTED: "answer their question, then invite them to order the product discussed",
    Stage.PROFILING: "ask the single next intake question — do not ask two at once",
    Stage.CONFIGURING: "collect the next missing order detail, one at a time",
    Stage.CONFIRMING: "get a clear yes or no on the summary already shown",
    Stage.ORDERED: "reassure about the existing order; only suggest add-ons if they ask",
    Stage.POST_PURCHASE: "ask how they found it, then suggest a refill or matching product",
}

# Deterministic CTA for zero-cost paths (templated / cached answers).
STAGE_CTA = {
    Stage.NEW: "What are you looking for today?",
    Stage.BROWSING: "What would you like to work on — hair fall, dandruff, dryness or frizz?",
    Stage.INTERESTED: "Would you like me to add it to an order?",
    Stage.PROFILING: None,      # the intake question IS the CTA
    Stage.CONFIGURING: None,    # the slot question IS the CTA
    Stage.CONFIRMING: "Reply YES to confirm, or NO to change anything.",
    Stage.ORDERED: None,        # do not upsell over a pending order
    Stage.POST_PURCHASE: "Would you like to reorder?",
}


@dataclass
class SalesContext:
    stage: Stage
    next_action: str
    known: dict = field(default_factory=dict)
    last_product: str | None = None
    open_order: str | None = None
    order_count: int = 0

    @property
    def cta(self) -> str | None:
        return STAGE_CTA.get(self.stage)

    def as_prompt_block(self) -> str:
        """Injected into every composed reply so the model advances the sale."""
        lines = [f"CONVERSATION STAGE: {self.stage.value}", f"YOUR GOAL NOW: {self.next_action}"]
        if self.known:
            lines.append(f"WHAT YOU ALREADY KNOW: {self.known}")
            lines.append("Do NOT ask again for anything listed above.")
        if self.last_product:
            lines.append(f"PRODUCT UNDER DISCUSSION: {self.last_product}")
        if self.open_order:
            lines.append(f"THEY HAVE AN OPEN ORDER: {self.open_order}")
        if self.order_count > 1:
            lines.append(f"REPEAT CUSTOMER: {self.order_count} previous orders")
        return "\n".join(lines)

    def as_trace(self) -> dict:
        return {"stage": self.stage.value, "known": list(self.known.keys())}


async def derive(
    db: AsyncSession,
    tenant: Tenant,
    customer: Customer,
    state: dict,
    *,
    history_len: int = 0,
) -> SalesContext:
    """Work out where this conversation actually is, from facts on record."""
    state = state or {}
    order_draft = state.get("order") or {}
    consult = state.get("consult") or {}
    awaiting = state.get("awaiting")
    flow = state.get("flow")

    result = await db.execute(
        select(Order)
        .where(Order.tenant_id == tenant.id, Order.customer_id == customer.id)
        .order_by(Order.created_at.desc())
        .limit(5)
    )
    orders = result.scalars().all()

    known: dict = {}
    profile = customer.profile or {}
    for key in ("hair_type", "concern", "budget"):
        if profile.get(key):
            known[key] = profile[key]
    if customer.name:
        known["name"] = customer.name
    for key in ("name", "address", "pincode", "payment_method", "quantity"):
        if order_draft.get(key):
            known[key] = order_draft[key]

    last_product = order_draft.get("product") or state.get("last_product")

    # Order of checks matters: the most specific live state wins.
    if awaiting == "confirm":
        stage = Stage.CONFIRMING
    elif flow == "order" or order_draft.get("sku"):
        stage = Stage.CONFIGURING
    elif flow == "consultation" or (consult and not consult.get("budget")):
        stage = Stage.PROFILING
    elif orders:
        latest = orders[0]
        recent = latest.created_at > datetime.now(timezone.utc) - timedelta(days=30)
        if latest.status == "delivered":
            stage = Stage.POST_PURCHASE
        elif recent and latest.status not in ("cancelled",):
            stage = Stage.ORDERED
        else:
            stage = Stage.POST_PURCHASE
    elif last_product:
        stage = Stage.INTERESTED
    elif history_len > 0:
        stage = Stage.BROWSING
    else:
        stage = Stage.NEW

    open_order = None
    if stage in (Stage.ORDERED, Stage.CONFIRMING) and orders:
        open_order = f"{orders[0].order_number} ({orders[0].status})"

    return SalesContext(
        stage=stage,
        next_action=NEXT_ACTION[stage],
        known=known,
        last_product=last_product,
        open_order=open_order,
        order_count=len(orders),
    )
