"""Deterministic intent classifier — the confidence gate in front of the LLM router.

Purpose: only pay for a model call when the message is genuinely ambiguous.
Roughly half to two-thirds of real messages have an unmistakable intent
("where is my order", a bare SKU from a deep link, "price?"), and those should
cost nothing.

Design contract: **high precision, low recall.** Returning None is free — the
LLM router handles it. Returning the *wrong* intent confidently is expensive,
because it sends the customer down the wrong flow. So every rule here is
deliberately narrow, and anything advisory is refused outright.

The highest-value case is entry-point context: a customer who taps a "Chat about
this product" button or scans a QR on the packaging arrives with the product
already known. That is a zero-AI path from first message to paid order.
"""

import re
from dataclasses import dataclass, field

from app.pipeline.text_signals import is_advisory

# --- deep-link / entry-point encoding -------------------------------------
#
# Put one of these in the prefilled text of a wa.me link, an ad, or a QR code:
#     https://wa.me/<number>?text=PRODUCT%3A%20ARG-OIL-100
#     https://wa.me/<number>?text=%23ARG-OIL-100
# The first inbound message then names the SKU, so no inference is needed.
SKU_PATTERNS = (
    re.compile(r"\bproduct\s*[:#=]\s*([A-Za-z0-9][A-Za-z0-9\-_]{2,30})", re.I),
    re.compile(r"\bsku\s*[:#=]\s*([A-Za-z0-9][A-Za-z0-9\-_]{2,30})", re.I),
    re.compile(r"\bref\s*[:#=]\s*([A-Za-z0-9][A-Za-z0-9\-_]{2,30})", re.I),
    re.compile(r"#([A-Z0-9]{3,}(?:-[A-Z0-9]+){1,3})\b"),
)

ORDER_STATUS_PATTERNS = (
    "where is my order", "where is my parcel", "order status", "status of my order",
    "track my order", "tracking", "tracking id", "has it shipped", "have you shipped",
    "when will it arrive", "when will i get", "not delivered yet", "any update on my order",
    "shipped or not", "dispatch status", "shipped yet", "where is my package",
    "my parcel", "my package", "my shipment", "delivery status",
)

ORDER_INTENT_PATTERNS = (
    "i want to order", "i want to buy", "i would like to order", "please order",
    "place an order", "place my order", "book it", "i will take", "ill take",
    "i want it", "send me one", "send me 1", "order this", "buy this",
    "confirm my order", "i want to purchase",
)

PRICE_PATTERNS = (
    "how much", "what is the price", "whats the price", "price of", "price?",
    "cost of", "how much is", "how much for", "rate of", "mrp",
)

STOCK_PATTERNS = (
    "in stock", "available", "availability", "do you have", "is it there",
    "out of stock", "restock",
)

PAYMENT_PATTERNS = (
    "how do i pay", "how to pay", "payment link", "payment failed", "upi id",
    "send me the link", "qr code", "resend link",
)

AFFIRMATIVE = (
    "yes", "yes please", "yep", "yeah", "ok", "okay", "sure", "confirm",
    "confirmed", "go ahead", "done", "correct", "right", "proceed", "book it",
    "y", "ya", "haan", "yes ok",
)

NEGATIVE = ("no", "nope", "not now", "later", "cancel", "dont", "do not", "stop")


@dataclass
class FastIntent:
    intent: str
    confidence: float
    slots: dict = field(default_factory=dict)
    reason: str = ""


def extract_sku(text: str) -> str | None:
    """Pull a product code out of a deep-link / QR / ad prefilled message."""
    for pattern in SKU_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return match.group(1).upper()
    return None


def is_affirmative(normalized: str) -> bool:
    stripped = re.sub(r"[^\w\s]", "", normalized).strip()
    return stripped in AFFIRMATIVE


def is_negative(normalized: str) -> bool:
    stripped = re.sub(r"[^\w\s]", "", normalized).strip()
    return stripped in NEGATIVE or any(
        stripped.startswith(word) for word in ("no ", "not ", "dont ", "cancel")
    )


def _product_phrase_after(normalized: str, markers: tuple[str, ...]) -> str | None:
    """Best-effort product name from "i want to order the tea tree shampoo"."""
    for marker in markers:
        if marker in normalized:
            tail = normalized.split(marker, 1)[1].strip()
            tail = re.sub(r"^(the|a|an|one|1|some|this|that)\s+", "", tail).strip()
            tail = re.sub(r"[?.!,]+$", "", tail).strip()
            if 2 < len(tail) <= 60:
                return tail
    return None


def classify(
    normalized: str,
    raw_message: str,
    *,
    state: dict | None = None,
    entry_context: dict | None = None,
) -> FastIntent | None:
    """Return a confident intent, or None to defer to the LLM router."""
    state = state or {}
    entry_context = entry_context or {}

    # 1. Entry point already told us the product. Strongest possible signal.
    if entry_context.get("sku") or entry_context.get("product"):
        return FastIntent(
            intent="order_capture",
            confidence=1.0,
            slots={
                k: v
                for k, v in (
                    ("sku", entry_context.get("sku")),
                    ("product", entry_context.get("product")),
                )
                if v
            },
            reason="entry_point_context",
        )

    # 2. Deep link / QR / ad prefilled text naming a SKU.
    sku = extract_sku(raw_message)
    if sku:
        return FastIntent(
            intent="order_capture",
            confidence=1.0,
            slots={"sku": sku},
            reason="deep_link_sku",
        )

    if not normalized:
        return None

    # 3. Mid-flow confirmations. "yes" after a summary means create the order.
    if state.get("awaiting") == "confirm":
        if is_affirmative(normalized):
            return FastIntent("order_capture", 1.0, {"confirm": True}, "confirm_yes")
        if is_negative(normalized):
            return FastIntent("order_capture", 1.0, {"confirm": False}, "confirm_no")

    # Advisory questions are never handled here — that is where selling happens.
    if is_advisory(normalized):
        return None

    # 4. Order status.
    if any(p in normalized for p in ORDER_STATUS_PATTERNS):
        return FastIntent("order_status", 0.95, {}, "status_pattern")

    # 5. Explicit intent to buy.
    if any(p in normalized for p in ORDER_INTENT_PATTERNS):
        product = _product_phrase_after(normalized, ORDER_INTENT_PATTERNS)
        slots = {"product": product} if product else {}
        return FastIntent("order_capture", 0.9, slots, "order_pattern")

    # 6. Payment mechanics.
    if any(p in normalized for p in PAYMENT_PATTERNS):
        return FastIntent("payment", 0.9, {}, "payment_pattern")

    # 7. Price / stock questions -> grounded catalog lookup, no routing needed.
    if any(p in normalized for p in PRICE_PATTERNS) or any(
        p in normalized for p in STOCK_PATTERNS
    ):
        return FastIntent("catalog_qa", 0.9, {}, "price_stock_pattern")

    # Uncertain. Defer to the model — this is the case it is worth paying for.
    return None
