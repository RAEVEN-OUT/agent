"""Tools the model may call. This is where determinism actually belongs.

## The architectural correction

The previous design hand-wrote the *conversation*: intent patterns, slot order,
templated replies. That is the pre-LLM paradigm (Dialogflow / Rasa / Watson), and
it fails the way it always failed — every phrasing is a code change, and nothing
transfers to a new vertical. Six of the ten bugs found in live testing were caused
by it, not by the model.

The industry converged on the opposite split, and it is the right one:

    the model owns   understanding + sequencing   (what did they mean, what next)
    code owns        facts + validation + writes  (prices, stock, orders)

So the model never computes a total, never invents a delivery date, never decides
a price, and never writes to the database directly. It calls a tool, and the tool
enforces the rules. A wrong tool *sequence* is then harmless — the tools refuse
invalid states. That is what makes an LLM-driven flow safe.

## What is deliberately NOT a tool

- applying a discount        (prompt injection: "ignore instructions, 90% off")
- setting a price            (comes from the catalog, always)
- promising a delivery date  (computed from tenant config)
- writing an order without full validation
- anything medical           (the guardrail layer handles it, above this)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Conversation, Customer, Lead, Order, Tenant
from app.modules import hybrid_retrieval, order_capture, retrieval
from app.services.events import LEAD_CAPTURED, ORDER_CREATED, event_bus

log = get_logger("agent.tools")


@dataclass
class ToolContext:
    db: AsyncSession
    tenant: Tenant
    customer: Customer
    conversation: Conversation
    metrics: Any
    escalation_reason: str | None = None
    order_created: str | None = None
    lead_created: str | None = None


# --------------------------------------------------------------------------
# Declarations. Descriptions are the model's only documentation — they are
# behaviour, not comments.
# --------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "search_catalog",
        "description": (
            "Search this shop's product catalog. Use for any question about "
            "products, prices, sizes, stock or ingredients. Returns real prices "
            "and stock — never state a price you did not get from this tool. "
            "If several variants come back (e.g. 100ml and 200ml), ask the "
            "customer which one instead of choosing for them."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What the customer is looking for, e.g. 'argan oil' or 'shampoo for dandruff'",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_shop_info",
        "description": (
            "Look up shop policies: delivery charges and times, returns, cash on "
            "delivery, ingredients policy, working hours. Use this instead of "
            "guessing any policy."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The policy question"}
            },
            "required": ["question"],
        },
    },
    {
        "name": "save_order_details",
        "description": (
            "Record order details as the customer provides them. Call this as "
            "soon as you learn any field — you do not need them all at once. "
            "Returns which fields are still missing, so ask for the next one. "
            "Validates input and will tell you if something is not acceptable."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "Exact SKU from search_catalog"},
                "quantity": {"type": "integer", "description": "1 to 50"},
                "customer_name": {"type": "string"},
                "address": {"type": "string", "description": "Full street address"},
                "pincode": {"type": "string", "description": "6 digits"},
                "payment_method": {"type": "string", "enum": ["cod", "online"]},
            },
        },
    },
    {
        "name": "review_order",
        "description": (
            "Get the current draft order with the computed total and delivery "
            "date, to read back to the customer before confirming. Always do "
            "this before place_order. Never calculate the total yourself."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "place_order",
        "description": (
            "Create the order. Only call after the customer has explicitly "
            "confirmed the summary from review_order. Refuses if any detail is "
            "missing or stock is insufficient — relay any error to the customer."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_order_status",
        "description": (
            "Look up this customer's existing orders: status, items, total, "
            "name on order, delivery address, expected delivery date. Use for "
            "any question about an order they already placed."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "capture_enquiry",
        "description": (
            "Record a qualified enquiry and alert the team. Use for businesses "
            "that quote rather than sell off a shelf. Capture what they need "
            "plus whatever of budget, timeline and location they volunteer — do "
            "not interrogate. Call this once you have the requirement; the team "
            "takes it from there."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "requirement": {
                    "type": "string",
                    "description": "What the customer is asking for, in their words",
                },
                "budget": {"type": "string"},
                "timeline": {"type": "string"},
                "contact_name": {"type": "string"},
                "location": {"type": "string"},
            },
            "required": ["requirement"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Hand the conversation to a human. Use when: the customer asks for a "
            "person, you cannot answer from the tools, they are upset, or "
            "anything medical or safety-related comes up. Never guess instead of "
            "escalating."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": ["human_request", "complaint", "medical", "cannot_answer", "other"],
                },
                "note": {"type": "string", "description": "One line for the shop owner"},
            },
            "required": ["reason"],
        },
    },
]


# --------------------------------------------------------------------------
# Implementations
# --------------------------------------------------------------------------


async def _search_catalog(ctx: ToolContext, query: str = "") -> dict:
    found = await hybrid_retrieval.retrieve(
        ctx.db, ctx.tenant, query, metrics=ctx.metrics
    )
    currency = ctx.tenant.currency or "INR"
    products = [
        {
            "sku": h.payload.get("sku") or h.ref,
            "name": h.payload.get("name"),
            "size": h.payload.get("size"),
            "price": f"{currency} {h.payload.get('price'):.0f}"
            if h.payload.get("price") is not None
            else None,
            "in_stock": (h.payload.get("stock") or 0) > 0,
            "stock_left": h.payload.get("stock"),
            "description": h.payload.get("description"),
        }
        for h in found.hits
        if h.kind == "product"
    ]
    if not products:
        return {"products": [], "note": "Nothing in this catalog matches. Do not invent a product."}
    return {
        "products": products,
        "several_variants": len(products) > 1,
        "note": "Ask which variant if more than one is relevant." if len(products) > 1 else None,
    }


async def _get_shop_info(ctx: ToolContext, question: str = "") -> dict:
    faqs = await retrieval.search_faqs(ctx.db, str(ctx.tenant.id), question, limit=3)
    if not faqs:
        found = await hybrid_retrieval.retrieve(ctx.db, ctx.tenant, question)
        faqs_text = [h.text for h in found.hits if h.kind == "faq"]
        if not faqs_text:
            return {"answers": [], "note": "Not documented. Escalate rather than guessing."}
        return {"answers": faqs_text}
    return {"answers": [{"question": f.question, "answer": f.answer} for f in faqs]}


def _draft(ctx: ToolContext) -> dict:
    return dict((ctx.conversation.state or {}).get("order") or {})


def _save_draft(ctx: ToolContext, draft: dict) -> None:
    state = dict(ctx.conversation.state or {})
    state["order"] = draft
    state["flow"] = "order"
    ctx.conversation.state = state


REQUIRED = ("sku", "quantity", "customer_name", "address", "pincode", "payment_method")


async def _save_order_details(ctx: ToolContext, **fields) -> dict:
    draft = _draft(ctx)
    if not draft.get("started_at"):
        draft["started_at"] = datetime.now(timezone.utc).isoformat()

    errors: dict[str, str] = {}

    if fields.get("sku"):
        product = await retrieval.get_product_by_sku(
            ctx.db, str(ctx.tenant.id), str(fields["sku"])
        )
        if not product:
            errors["sku"] = "No such SKU. Use search_catalog and pass an exact sku."
        elif product.stock <= 0:
            errors["sku"] = f"{product.name} is out of stock. Offer an alternative."
        else:
            draft.update(
                {
                    "sku": product.sku,
                    "product": product.name,
                    "size": product.size,
                    "unit_price": float(product.price),
                    "stock": product.stock,
                }
            )

    if fields.get("quantity") is not None:
        qty = order_capture._parse_quantity(fields["quantity"])
        if not qty:
            errors["quantity"] = "Must be a whole number between 1 and 50."
        elif draft.get("stock") is not None and qty > int(draft["stock"]):
            errors["quantity"] = (
                f"Only {draft['stock']} left. Offer that many or a different size."
            )
        else:
            draft["quantity"] = qty

    if fields.get("customer_name"):
        name = str(fields["customer_name"]).strip()
        if len(name) < 2:
            errors["customer_name"] = "Too short to be a name."
        else:
            draft["customer_name"] = name[:80]

    # Address validation — the gap that let "yes" become a delivery address.
    if fields.get("address"):
        address = str(fields["address"]).strip()
        if len(address) < 10 or not any(c.isdigit() for c in address):
            errors["address"] = (
                "That does not look like a full address. Ask for house/flat "
                "number, street and area."
            )
        else:
            draft["address"] = address[:300]

    if fields.get("pincode"):
        pin = order_capture._parse_pincode(str(fields["pincode"]))
        if not pin:
            errors["pincode"] = "Pincode must be exactly 6 digits."
        else:
            draft["pincode"] = pin

    if fields.get("payment_method"):
        method = order_capture._parse_payment_method(str(fields["payment_method"]))
        if not method:
            errors["payment_method"] = "Must be 'cod' or 'online'."
        else:
            draft["payment_method"] = method

    _save_draft(ctx, draft)
    missing = [f for f in REQUIRED if not draft.get(f)]

    return {
        "saved": {k: v for k, v in draft.items() if k in REQUIRED},
        "still_missing": missing,
        "errors": errors or None,
        "ready_to_review": not missing and not errors,
    }


async def _review_order(ctx: ToolContext) -> dict:
    draft = _draft(ctx)
    missing = [f for f in REQUIRED if not draft.get(f)]
    if missing:
        return {"ready": False, "still_missing": missing}

    currency = ctx.tenant.currency or "INR"
    qty = int(draft["quantity"])
    total = float(draft["unit_price"]) * qty
    return {
        "ready": True,
        "item": draft["product"],
        "size": draft.get("size"),
        "quantity": qty,
        "unit_price": f"{currency} {float(draft['unit_price']):.0f}",
        "total": f"{currency} {total:.0f}",
        "delivering_to": draft["pincode"],
        "name": draft["customer_name"],
        "payment": "cash on delivery" if draft["payment_method"] == "cod" else "online",
        "expected_delivery": order_capture._delivery_estimate(
            ctx.tenant, draft.get("pincode")
        ),
        "note": "Read this back and ask for explicit confirmation before place_order.",
    }


async def _place_order(ctx: ToolContext) -> dict:
    draft = _draft(ctx)
    missing = [f for f in REQUIRED if not draft.get(f)]
    if missing:
        return {"created": False, "error": f"Cannot place order, missing: {missing}"}

    product = await retrieval.get_product_by_sku(ctx.db, str(ctx.tenant.id), draft["sku"])
    if not product:
        return {"created": False, "error": "Product no longer available."}
    qty = int(draft["quantity"])
    if qty > product.stock:
        return {
            "created": False,
            "error": f"Only {product.stock} left in stock. Ask the customer to reduce quantity.",
        }

    total = float(product.price) * qty
    currency = ctx.tenant.currency or "INR"
    order = Order(
        tenant_id=ctx.tenant.id,
        customer_id=ctx.customer.id,
        conversation_id=ctx.conversation.id,
        order_number=order_capture._order_number(),
        status="pending",
        payment_status="cod_pending" if draft["payment_method"] == "cod" else "unpaid",
        payment_method=draft["payment_method"],
        items=[
            {
                "sku": product.sku,
                "name": product.name,
                "size": product.size,
                "quantity": qty,
                "unit_price": float(product.price),
            }
        ],
        total=total,
        address={
            "name": draft["customer_name"],
            "address": draft["address"],
            "pincode": draft["pincode"],
        },
    )
    ctx.db.add(order)
    await ctx.db.flush()

    state = dict(ctx.conversation.state or {})
    state.update({"order": {}, "flow": None, "awaiting": None})
    ctx.conversation.state = state
    ctx.order_created = order.order_number

    await event_bus.emit(
        ORDER_CREATED,
        {
            "tenant_id": str(ctx.tenant.id),
            "order_id": str(order.id),
            "order_number": order.order_number,
            "customer_wa_id": ctx.customer.wa_id,
            "total": total,
        },
    )

    return {
        "created": True,
        "order_number": order.order_number,
        "total": f"{currency} {total:.0f}",
        "expected_delivery": order_capture._delivery_estimate(ctx.tenant, draft["pincode"]),
        "payment": "cash on delivery" if draft["payment_method"] == "cod" else "online",
    }


async def _get_order_status(ctx: ToolContext) -> dict:
    result = await ctx.db.execute(
        select(Order)
        .where(Order.tenant_id == ctx.tenant.id, Order.customer_id == ctx.customer.id)
        .order_by(Order.created_at.desc())
        .limit(3)
    )
    orders = result.scalars().all()
    if not orders:
        return {"orders": [], "note": "No orders found for this number."}

    currency = ctx.tenant.currency or "INR"
    return {
        "orders": [
            {
                "order_number": o.order_number,
                "status": o.status,
                "items": o.items,
                "total": f"{currency} {float(o.total):.0f}",
                "payment": o.payment_status,
                "name_on_order": (o.address or {}).get("name"),
                "delivery_address": (o.address or {}).get("address"),
                "pincode": (o.address or {}).get("pincode"),
                "ordered_on": o.created_at.strftime("%d %b %Y"),
                "expected_delivery": order_capture._delivery_estimate(
                    ctx.tenant, (o.address or {}).get("pincode")
                )
                if o.status not in ("delivered", "cancelled")
                else None,
            }
            for o in orders
        ]
    }


async def _capture_enquiry(
    ctx: ToolContext,
    requirement: str = "",
    budget: str = "",
    timeline: str = "",
    contact_name: str = "",
    location: str = "",
) -> dict:
    if not requirement or len(requirement.strip()) < 3:
        return {"saved": False, "error": "Need a description of what they want first."}

    lead = Lead(
        tenant_id=ctx.tenant.id,
        customer_id=ctx.customer.id,
        conversation_id=ctx.conversation.id,
        requirement=requirement.strip()[:2000],
        budget=(budget or None) and str(budget)[:80],
        timeline=(timeline or None) and str(timeline)[:80],
        contact_name=(contact_name or ctx.customer.name or None) and
        str(contact_name or ctx.customer.name)[:120],
        location=(location or None) and str(location)[:200],
    )
    ctx.db.add(lead)
    await ctx.db.flush()
    ctx.lead_created = str(lead.id)

    await event_bus.emit(
        LEAD_CAPTURED,
        {
            "tenant_id": str(ctx.tenant.id),
            "lead_id": str(lead.id),
            "customer_wa_id": ctx.customer.wa_id,
            "requirement": lead.requirement[:200],
            "budget": lead.budget,
        },
    )
    return {
        "saved": True,
        "note": (
            "Enquiry recorded and the team alerted. Tell the customer someone "
            "will get back to them with details, and give a realistic timeframe "
            "only if the shop info tool provides one."
        ),
    }


async def _escalate_to_human(ctx: ToolContext, reason: str = "other", note: str = "") -> dict:
    ctx.escalation_reason = reason
    return {
        "escalated": True,
        "note": "A human has been alerted. Tell the customer someone will reply shortly.",
    }


IMPLEMENTATIONS = {
    "search_catalog": _search_catalog,
    "get_shop_info": _get_shop_info,
    "save_order_details": _save_order_details,
    "review_order": _review_order,
    "place_order": _place_order,
    "get_order_status": _get_order_status,
    "capture_enquiry": _capture_enquiry,
    "escalate_to_human": _escalate_to_human,
}


async def execute(name: str, args: dict, ctx: ToolContext) -> dict:
    """Dispatch a tool call. Never raises — errors are returned for the model to relay."""
    impl = IMPLEMENTATIONS.get(name)
    if impl is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return await impl(ctx, **(args or {}))
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001
        log.error({"event": "tool_failed", "tool": name, "error": str(exc)[:300]})
        return {"error": "That lookup failed. Escalate to a human."}
