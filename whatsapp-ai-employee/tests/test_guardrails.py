"""Guardrail tests.

These are the highest-stakes tests in the project. A false negative here means
either an unanswered adverse reaction or a WhatsApp policy violation that can
get the client's business number banned.
"""

from app.pipeline.guardrails import (
    SAFE_FALLBACK,
    check_inbound,
    sanitize_outbound,
    scan_outbound,
)
from app.pipeline.normalize import normalize


class TestAdverseReactions:
    """Must always escalate, never auto-answer."""

    def test_burning_scalp(self):
        reason, _ = check_inbound(normalize("my scalp is burning after using the oil"))
        assert reason == "adverse_reaction"

    def test_allergic_reaction(self):
        reason, _ = check_inbound(normalize("i think i am allergic to this shampoo"))
        assert reason == "adverse_reaction"

    def test_rash(self):
        reason, _ = check_inbound(normalize("i got a rash on my forehead"))
        assert reason == "adverse_reaction"

    def test_itching(self):
        reason, _ = check_inbound(normalize("my head is itching a lot"))
        assert reason == "adverse_reaction"

    def test_swelling(self):
        reason, _ = check_inbound(normalize("my face is swollen"))
        assert reason == "adverse_reaction"


class TestMedicalQuestions:
    def test_named_condition(self):
        reason, _ = check_inbound(normalize("will this help with alopecia"))
        assert reason == "medical"

    def test_pregnancy(self):
        reason, _ = check_inbound(normalize("is it safe while pregnant"))
        assert reason == "medical"

    def test_drug_interaction(self):
        reason, _ = check_inbound(normalize("can i use it with minoxidil"))
        assert reason == "medical"

    def test_asks_for_diagnosis(self):
        reason, _ = check_inbound(normalize("can you diagnose my scalp problem"))
        assert reason == "medical"


class TestComplaints:
    def test_refund_request(self):
        reason, _ = check_inbound(normalize("i want my money back this is a scam"))
        assert reason == "complaint"

    def test_not_received(self):
        reason, _ = check_inbound(normalize("i still not received my order"))
        assert reason == "complaint"


class TestOrdinaryMessagesPassThrough:
    """Guardrails must not hijack normal sales conversations."""

    def test_normal_questions(self):
        for text in (
            "how much is the argan oil",
            "do you have 200ml",
            "which shampoo is good for dry hair",
            "i want to order the rosemary shampoo",
            "what are the delivery charges",
            "my hair is very dry and frizzy",
            "i have a lot of hair fall",  # a concern, not a medical question
            "is it sulphate free",
        ):
            assert check_inbound(normalize(text)) is None, text


class TestOutboundClaims:
    def test_blocks_cure_claim(self):
        assert scan_outbound("This oil cures hair fall permanently")

    def test_blocks_regrowth_promise(self):
        assert scan_outbound("It will regrow your hair in 30 days")

    def test_blocks_treatment_language(self):
        assert scan_outbound("This treats dandruff completely")

    def test_blocks_guarantee(self):
        assert scan_outbound("Guaranteed results in one month")

    def test_blocks_no_side_effects(self):
        assert scan_outbound("It has no side effects at all")

    def test_blocks_pregnancy_safety_claim(self):
        assert scan_outbound("Yes it is safe during pregnancy")

    def test_allows_compliant_description(self):
        for text in (
            "The Argan Repair Hair Oil is INR 449 for 100ml and is in stock.",
            "This shampoo is formulated for oily scalp and flaking. Would you like to order?",
            "It contains rosemary and biotin. Use it twice a week.",
            "Delivery is free above INR 599.",
        ):
            assert scan_outbound(text) == [], text

    def test_sanitize_replaces_violating_reply(self):
        text, violations = sanitize_outbound("This cures dandruff")
        assert violations
        assert text == SAFE_FALLBACK

    def test_sanitize_passes_clean_reply(self):
        original = "The oil is INR 449 and in stock."
        text, violations = sanitize_outbound(original)
        assert violations == []
        assert text == original
