"""Business templates — the productised unit you sell.

## The idea (yours, and it's the right one)

Rather than one generic bot configured per client, build a handful of complete
templates — consultancy-based, single-product, enquiry-based — and sell the one
that matches the client. They add their data; nothing is written for them.

A capability kit was only the tools. A **template** is the whole package, which
is what makes onboarding a form instead of a project:

    capabilities        which tools the model can call
    catalog schema      what fields their data needs
    intake questions    what to ask before recommending
    message templates   the WhatsApp templates to submit for approval
    policy questions    the FAQs they must fill in
    tone + goal         how it talks, and what counts as success

The last two rows matter more than they look. **Success is not the same in every
template**: a consultancy template succeeds when an order is placed; an
enquiry template succeeds when a good lead reaches a human. A bot that tries to
close a sale for an interior designer is behaving wrongly, not just sub-optimally.

## Why the WhatsApp template library is the real leverage

Outbound messages (order updates, reminders, refill nudges) each need Meta
approval before they can be sent. Those are vertical-specific: a bakery needs
"your cake is ready for pickup", a salon needs "your appointment is tomorrow at
4pm". Build the library once per template, and every future client in that
vertical inherits already-approved wording instead of waiting on review.
"""

from dataclasses import dataclass, field

from app.agent.capabilities import Capability


@dataclass(frozen=True)
class MessageTemplate:
    """A WhatsApp template to submit for approval. `body` uses {{1}} placeholders."""

    name: str
    category: str  # UTILITY | MARKETING
    body: str
    example: tuple[str, ...] = ()


@dataclass(frozen=True)
class BusinessTemplate:
    key: str
    label: str
    sells_to: str
    capabilities: tuple[Capability, ...]
    # What "done" looks like — shapes how hard the bot pushes toward a close.
    goal: str
    catalog_fields: tuple[str, ...]
    intake: tuple[dict, ...] = ()
    policy_questions: tuple[str, ...] = ()
    message_templates: tuple[MessageTemplate, ...] = ()
    tone: str = "warm, friendly, concise"
    notes: str = ""
    extra_prompt: str = ""


# --- shared outbound templates -------------------------------------------

ORDER_TEMPLATES = (
    MessageTemplate(
        "order_confirmed", "UTILITY",
        "Hi {{1}}, your order {{2}} is confirmed. Total {{3}}. "
        "We'll let you know as soon as it ships.",
        ("Aparna", "ORD1234", "INR 898"),
    ),
    MessageTemplate(
        "order_shipped", "UTILITY",
        "Good news {{1}} — order {{2}} has shipped and should arrive by {{3}}.",
        ("Aparna", "ORD1234", "Sun, 02 Aug"),
    ),
    MessageTemplate(
        "order_delivered_feedback", "UTILITY",
        "Hi {{1}}, your order {{2}} was delivered. How did you find it?",
        ("Aparna", "ORD1234"),
    ),
    MessageTemplate(
        "abandoned_enquiry", "MARKETING",
        "Hi {{1}}, you were looking at {{2}} earlier. Still interested? "
        "Reply STOP to opt out.",
        ("Aparna", "Argan Repair Hair Oil"),
    ),
)


TEMPLATES: dict[str, BusinessTemplate] = {
    # ---------------------------------------------------------------
    "consultancy": BusinessTemplate(
        key="consultancy",
        label="Consultancy-based selling",
        sells_to="hair care, skincare, supplements, nutrition, pet care",
        capabilities=(
            Capability.CATALOG, Capability.CONSULTATION, Capability.ORDERING,
            Capability.ORDER_STATUS, Capability.SHOP_INFO,
        ),
        goal="place an order after recommending the right product",
        catalog_fields=("sku", "name", "size", "price", "stock", "concern", "suited_to", "description"),
        intake=(
            {"slot": "concern", "question": "What would you like to work on?"},
            {"slot": "type", "question": "How would you describe your hair/skin type?"},
            {"slot": "budget", "question": "Any budget you'd like me to stay within?"},
        ),
        policy_questions=(
            "What are the delivery charges?",
            "How long does delivery take?",
            "Do you offer cash on delivery?",
            "What is your return policy?",
            "Are the products vegan / cruelty free?",
            "What are your working hours?",
        ),
        message_templates=ORDER_TEMPLATES + (
            MessageTemplate(
                "refill_reminder", "MARKETING",
                "Hi {{1}}, your {{2}} should be running low around now. "
                "Want me to reorder it? Reply STOP to opt out.",
                ("Aparna", "Argan Repair Hair Oil 200ml"),
            ),
        ),
        notes="Refill reminders are the strongest retention lever here — consumable sizes make repurchase timing predictable.",
        extra_prompt=(
            "This shop sells by advice. Ask at most two short qualifying questions, "
            "then recommend specific products with a one-line reason each."
        ),
    ),
    # ---------------------------------------------------------------
    "single_product": BusinessTemplate(
        key="single_product",
        label="Single-product selling",
        sells_to="one hero product, a course, a device, a subscription box",
        capabilities=(
            Capability.ORDERING, Capability.ORDER_STATUS, Capability.SHOP_INFO,
        ),
        goal="answer objections and close the one product",
        catalog_fields=("sku", "name", "price", "stock", "description"),
        policy_questions=(
            "What are the delivery charges?",
            "How long does delivery take?",
            "Do you offer cash on delivery?",
            "What is your refund policy?",
            "What makes it different from alternatives?",
        ),
        message_templates=ORDER_TEMPLATES,
        notes="No catalog search — there is nothing to browse. Deep links (wa.me?text=PRODUCT:SKU) go straight to ordering.",
        extra_prompt=(
            "There is ONE product. Never ask which product they want. Handle "
            "objections about price and suitability, then move to ordering."
        ),
    ),
    # ---------------------------------------------------------------
    "enquiry": BusinessTemplate(
        key="enquiry",
        label="Enquiry / lead capture",
        sells_to="real estate, interiors, B2B, custom fabrication, event services",
        capabilities=(
            Capability.ENQUIRY, Capability.SHOP_INFO,
        ),
        goal="qualify the enquiry and hand a good lead to a human — never quote a price",
        catalog_fields=("service", "description", "starting_from", "coverage_area"),
        intake=(
            {"slot": "requirement", "question": "What are you looking for?"},
            {"slot": "location", "question": "Which area are you in?"},
            {"slot": "timeline", "question": "When are you hoping to get started?"},
            {"slot": "budget", "question": "Do you have a budget range in mind?"},
        ),
        policy_questions=(
            "Which areas do you serve?",
            "What is the typical project timeline?",
            "Do you charge for a consultation?",
            "What are your working hours?",
        ),
        message_templates=(
            MessageTemplate(
                "enquiry_received", "UTILITY",
                "Thanks {{1}} — we have your enquiry about {{2}}. "
                "Our team will call you within {{3}}.",
                ("Aparna", "a 2BHK interior", "24 hours"),
            ),
            MessageTemplate(
                "enquiry_followup", "MARKETING",
                "Hi {{1}}, following up on your enquiry about {{2}}. "
                "Still looking? Reply STOP to opt out.",
                ("Aparna", "a 2BHK interior"),
            ),
        ),
        notes="CRITICAL: the bot must NOT quote prices or promise scope. Quoting is the human's job — a wrong number here loses money or trust.",
        extra_prompt=(
            "You do NOT sell or quote. Your job is to understand the requirement "
            "and capture it so the team can follow up. Never state a price or a "
            "total, even if asked — say the team will prepare a quote. Capture the "
            "enquiry as soon as you understand the requirement; do not interrogate."
        ),
    ),
    # ---------------------------------------------------------------
    "catalog": BusinessTemplate(
        key="catalog",
        label="Catalog / inventory selling",
        sells_to="boutiques, resellers, general stores, COD sellers",
        capabilities=(
            Capability.CATALOG, Capability.ORDERING,
            Capability.ORDER_STATUS, Capability.SHOP_INFO,
        ),
        goal="help them find an item in stock and order it",
        catalog_fields=("sku", "name", "variant", "size", "colour", "price", "stock", "description"),
        policy_questions=(
            "What are the delivery charges?",
            "How long does delivery take?",
            "Do you offer cash on delivery?",
            "What is your exchange policy?",
            "What are your working hours?",
        ),
        message_templates=ORDER_TEMPLATES + (
            MessageTemplate(
                "back_in_stock", "MARKETING",
                "Hi {{1}}, {{2}} is back in stock. Want me to reserve one? "
                "Reply STOP to opt out.",
                ("Aparna", "Blue Floral Maxi, size M"),
            ),
        ),
        notes="Variant ambiguity is the main risk — always confirm size/colour before ordering.",
    ),
    # ---------------------------------------------------------------
    "made_to_order": BusinessTemplate(
        key="made_to_order",
        label="Made to order",
        sells_to="home bakers, tailors, custom gifting, print shops",
        capabilities=(
            Capability.CATALOG, Capability.CONSULTATION, Capability.ORDERING,
            Capability.ORDER_STATUS, Capability.SHOP_INFO,
        ),
        goal="capture a complete custom spec, confirm lead time, then take the order",
        catalog_fields=("item", "base_price", "unit", "options", "lead_time_hours", "description"),
        intake=(
            {"slot": "occasion", "question": "What's the occasion?"},
            {"slot": "spec", "question": "Any preference on flavour/design?"},
            {"slot": "needed_by", "question": "When do you need it?"},
        ),
        policy_questions=(
            "How much notice do you need for an order?",
            "Do you deliver, or is it pickup only?",
            "Do you take a deposit?",
            "Can you handle allergies or dietary requirements?",
        ),
        message_templates=(
            MessageTemplate(
                "order_accepted", "UTILITY",
                "Hi {{1}}, your order for {{2}} is confirmed for {{3}}. Total {{4}}.",
                ("Aparna", "1kg chocolate cake", "Sat, 02 Aug", "INR 1200"),
            ),
            MessageTemplate(
                "ready_for_pickup", "UTILITY",
                "Hi {{1}}, your {{2}} is ready for pickup.",
                ("Aparna", "chocolate cake"),
            ),
        ),
        notes="Capacity, not stock, is the constraint. Never accept an order inside the lead time — confirm the date is possible first.",
        extra_prompt=(
            "Everything is made to order, so LEAD TIME matters more than stock. "
            "Confirm the date is achievable before agreeing to anything. Never "
            "promise a date the shop info does not support."
        ),
    ),
}

DEFAULT_TEMPLATE = "consultancy"


def get(key: str | None) -> BusinessTemplate:
    return TEMPLATES.get(key or DEFAULT_TEMPLATE, TEMPLATES[DEFAULT_TEMPLATE])


def for_tenant(tenant) -> BusinessTemplate:
    return get((tenant.settings or {}).get("template"))


def onboarding_checklist(key: str) -> list[str]:
    """What a new client must provide. This is the sales/onboarding form."""
    template = get(key)
    items = [
        f"Business name, and one paragraph describing what you sell",
        f"Catalog with these columns: {', '.join(template.catalog_fields)}",
    ]
    if template.policy_questions:
        items.append("Answers to these policy questions:")
        items += [f"    - {q}" for q in template.policy_questions]
    if template.message_templates:
        items.append(
            f"{len(template.message_templates)} WhatsApp templates to submit for "
            "approval (pre-written — no wording needed from you)"
        )
    items.append("WhatsApp Business number + Meta business verification")
    return items
