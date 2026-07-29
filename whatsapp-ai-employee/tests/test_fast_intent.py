"""Confidence-gated router tests.

Contract: HIGH PRECISION, LOW RECALL. Returning None is free (the LLM router
picks it up). Returning a confident *wrong* intent sends the customer down the
wrong flow, which is the expensive mistake. So these tests care much more about
false positives than about coverage.
"""

from app.pipeline.fast_intent import (
    classify,
    extract_sku,
    is_affirmative,
    is_negative,
)
from app.pipeline.normalize import normalize


def c(text: str, **kw):
    return classify(normalize(text), text, **kw)


class TestEntryPointContext:
    """The zero-AI path: customer taps a product button or scans a QR."""

    def test_entry_context_sku_goes_straight_to_order(self):
        result = c("hi", entry_context={"sku": "ARG-OIL-100"})
        assert result is not None
        assert result.intent == "order_capture"
        assert result.slots["sku"] == "ARG-OIL-100"
        assert result.confidence == 1.0
        assert result.reason == "entry_point_context"

    def test_deep_link_prefilled_text(self):
        result = c("PRODUCT: ROSE-SHM-200")
        assert result.intent == "order_capture"
        assert result.slots["sku"] == "ROSE-SHM-200"

    def test_hash_style_deep_link(self):
        result = c("#TEA-SHM-200")
        assert result.intent == "order_capture"
        assert result.slots["sku"] == "TEA-SHM-200"

    def test_sku_marker_variants(self):
        for text in ("sku: ARG-OIL-200", "ref=CURL-CRM-150", "PRODUCT#ROSE-CON-200"):
            assert extract_sku(text) is not None, text

    def test_plain_message_has_no_sku(self):
        for text in ("hello", "how much is the oil", "i need a shampoo for dry hair"):
            assert extract_sku(text) is None, text


class TestConfidentIntents:
    def test_order_status(self):
        for text in (
            "where is my order",
            "order status please",
            "has it shipped",
            "track my order",
            "when will it arrive",
            "has my parcel shipped yet",
            "any update on my order",
        ):
            result = c(text)
            assert result is not None and result.intent == "order_status", text

    def test_explicit_order_intent(self):
        result = c("i want to order the tea tree shampoo")
        assert result.intent == "order_capture"
        assert "tea tree shampoo" in result.slots.get("product", "")

    def test_price_question(self):
        for text in ("how much is the argan oil", "price of the serum", "what is the price"):
            result = c(text)
            assert result is not None and result.intent == "catalog_qa", text

    def test_stock_question(self):
        result = c("do you have the 200ml")
        assert result is not None and result.intent == "catalog_qa"

    def test_payment_question(self):
        result = c("how do i pay")
        assert result is not None and result.intent == "payment"


class TestRefusesToGuess:
    """Anything needing judgement must defer to the model."""

    def test_advisory_defers(self):
        for text in (
            "which shampoo is good for dandruff",
            "what should i use for hair fall",
            "suggest something for dry hair",
            "argan oil or serum which is better",
            "is this suitable for curly hair",
            "help me choose",
        ):
            assert c(text) is None, text

    def test_open_ended_defers(self):
        for text in (
            "my hair keeps breaking after i colored it",
            "i have been losing a lot of hair lately",
            "my daughter has very frizzy hair",
        ):
            assert c(text) is None, text

    def test_advisory_beats_price_pattern(self):
        # Contains "how much" but is really asking for advice — must not be
        # captured by the cheap price rule.
        assert c("how much should i use for dry hair") is None

    def test_empty_defers(self):
        assert c("") is None


class TestConfirmations:
    def test_affirmative_confirms_order(self):
        result = c("yes", state={"awaiting": "confirm"})
        assert result.intent == "order_capture"
        assert result.slots["confirm"] is True

    def test_negative_cancels(self):
        result = c("no", state={"awaiting": "confirm"})
        assert result.slots["confirm"] is False

    def test_confirmation_words(self):
        for text in ("yes", "ok", "confirm", "go ahead", "sure", "haan"):
            assert is_affirmative(normalize(text)), text

    def test_negative_words(self):
        for text in ("no", "not now", "cancel"):
            assert is_negative(normalize(text)), text

    def test_yes_outside_confirm_context_is_not_hijacked(self):
        # Without an awaiting=confirm state, a bare "yes" is ambiguous and must
        # not be turned into an order confirmation.
        assert c("yes") is None
