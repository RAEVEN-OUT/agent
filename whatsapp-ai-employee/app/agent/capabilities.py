"""Per-tenant capability kits — how one codebase serves different business types.

## The question this answers

Some clients sell one product. Some need inventory search. Some need
need-based filtering. Some sell services and book appointments. Can one project
do all of it, or does each client need its own automation?

One project can — but only because the agent decides *sequencing*. Verticals then
differ by which **capabilities** are switched on, not by rewriting conversation
logic. That distinction is the whole architecture:

    a flow-based bot   -> new vertical = new flow chart  = new code
    a tool-based agent -> new vertical = new tool set    = config

## What actually varies between business types

| business | needs |
|---|---|
| single-product seller | ORDERING only (skip search entirely via a deep link) |
| boutique / reseller | CATALOG + ORDERING |
| hair care / skincare | CATALOG + ORDERING + CONSULTATION (need-based filtering) |
| home baker | ORDERING + CONSULTATION + LEAD_TIME (made to order, not stocked) |
| salon / clinic | BOOKING (+ CATALOG if they also sell products) |

Note that "single product" is not a *simpler flow* — it is the same ordering
capability with one catalog row. Nothing special is built for it.

## The honest limit

Products and services are genuinely different **data models**, not just config:
a product has stock; a service has time slots and staff capacity. So there are
two kits, and BOOKING needs its own tables before a salon can be onboarded.
Everything else is config.
"""

from enum import Enum


class Capability(str, Enum):
    CATALOG = "catalog"            # search products, answer price/stock questions
    ORDERING = "ordering"          # take an order end to end
    CONSULTATION = "consultation"  # profile a need, then recommend
    BOOKING = "booking"            # appointments / slots  (needs the booking tables)
    ORDER_STATUS = "order_status"  # look up existing orders
    SHOP_INFO = "shop_info"        # policies, delivery, returns


# Which tools each capability exposes to the model.
CAPABILITY_TOOLS: dict[Capability, tuple[str, ...]] = {
    Capability.CATALOG: ("search_catalog",),
    Capability.ORDERING: ("save_order_details", "review_order", "place_order"),
    Capability.CONSULTATION: ("search_catalog",),  # same tool, different prompting
    Capability.BOOKING: ("check_availability", "book_appointment"),  # not built yet
    Capability.ORDER_STATUS: ("get_order_status",),
    Capability.SHOP_INFO: ("get_shop_info",),
}

# Always available, regardless of business type.
ALWAYS_ON = ("escalate_to_human",)


# Preset kits. A new client picks one and uploads their data — no code.
KITS: dict[str, tuple[Capability, ...]] = {
    "single_product": (
        Capability.ORDERING,
        Capability.ORDER_STATUS,
        Capability.SHOP_INFO,
    ),
    "catalog_seller": (
        Capability.CATALOG,
        Capability.ORDERING,
        Capability.ORDER_STATUS,
        Capability.SHOP_INFO,
    ),
    "consultative_seller": (  # hair care, skincare, supplements
        Capability.CATALOG,
        Capability.CONSULTATION,
        Capability.ORDERING,
        Capability.ORDER_STATUS,
        Capability.SHOP_INFO,
    ),
    "made_to_order": (  # home bakers, custom tailoring
        Capability.CATALOG,
        Capability.CONSULTATION,
        Capability.ORDERING,
        Capability.ORDER_STATUS,
        Capability.SHOP_INFO,
    ),
    "service_provider": (  # salon, clinic, studio
        Capability.BOOKING,
        Capability.SHOP_INFO,
    ),
    "service_and_retail": (  # salon that also sells products
        Capability.BOOKING,
        Capability.CATALOG,
        Capability.ORDERING,
        Capability.ORDER_STATUS,
        Capability.SHOP_INFO,
    ),
}

DEFAULT_KIT = "consultative_seller"

# Guidance appended to the system prompt per capability, so the model knows how
# this business actually operates. This is the "behaves accordingly" part.
CAPABILITY_PROMPTS: dict[Capability, str] = {
    Capability.CONSULTATION: (
        "This shop sells by advice. When someone describes a need or problem, "
        "ask at most two short qualifying questions, then recommend specific "
        "products from the catalog with a one-line reason each."
    ),
    Capability.BOOKING: (
        "This business books appointments. Check availability before offering "
        "any time. Never invent a slot. Confirm date, time and service before "
        "booking."
    ),
    Capability.ORDERING: (
        "You can take orders end to end. Collect details one at a time, read the "
        "summary back with the total, and only place the order after an explicit yes."
    ),
}


def kit_for(tenant) -> tuple[Capability, ...]:
    """Capabilities for a tenant: explicit list, else its kit, else the default."""
    config = tenant.settings or {}

    explicit = config.get("capabilities")
    if isinstance(explicit, list) and explicit:
        resolved = []
        for name in explicit:
            try:
                resolved.append(Capability(name))
            except ValueError:
                continue
        if resolved:
            return tuple(resolved)

    kit_name = config.get("kit") or DEFAULT_KIT
    return KITS.get(kit_name, KITS[DEFAULT_KIT])


def allowed_tools(tenant) -> set[str]:
    """Tool names this tenant's agent may call."""
    names: set[str] = set(ALWAYS_ON)
    for capability in kit_for(tenant):
        names.update(CAPABILITY_TOOLS.get(capability, ()))
    return names


def prompt_additions(tenant) -> str:
    """Per-capability behavioural guidance for the system prompt."""
    parts = [
        CAPABILITY_PROMPTS[c]
        for c in kit_for(tenant)
        if c in CAPABILITY_PROMPTS
    ]
    return "\n".join(parts)
