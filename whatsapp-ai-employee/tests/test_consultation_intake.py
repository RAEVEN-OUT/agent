"""Intake slot-filling tests.

Regression origin: a real conversation where the bot asked "Any budget you'd
like me to stay within?", the customer answered "none", then "no", and the bot
asked the identical question again both times. A loop is worse than a wrong
answer — the customer can correct a wrong value but cannot escape a loop.
"""

from app.modules.consultation import (
    DEFAULT_INTAKE,
    NO_PREFERENCE,
    _interpret_answer,
    _next_missing,
)
from app.pipeline.normalize import normalize


def interpret(slot: str, text: str):
    return _interpret_answer(slot, text, normalize(text))


class TestDeclineAnswers:
    """"no preference" is an ANSWER, not an absence of one."""

    def test_budget_declines(self):
        for text in ("none", "no", "any", "anything", "no budget", "doesnt matter",
                     "not sure", "skip", "whatever", "you decide"):
            assert interpret("budget", text) == NO_PREFERENCE, text

    def test_hair_type_decline(self):
        assert interpret("hair_type", "not sure") == NO_PREFERENCE

    def test_decline_never_returns_none(self):
        """Returning None is what caused the infinite loop."""
        for slot in ("hair_type", "concern", "budget"):
            for text in ("no", "none", "any"):
                assert interpret(slot, text) is not None


class TestBudgetParsing:
    def test_plain_number(self):
        assert interpret("budget", "500") == "500"

    def test_number_with_currency(self):
        assert interpret("budget", "under 1500 rupees") == "1500"

    def test_number_with_comma(self):
        assert interpret("budget", "2,000") == "2000"

    def test_non_numeric_stops_asking(self):
        # Must not loop just because we could not parse a number.
        assert interpret("budget", "something cheap") == NO_PREFERENCE


class TestFreeTextSlots:
    def test_hair_type_captured(self):
        assert interpret("hair_type", "dry") == "dry"

    def test_concern_captured(self):
        assert interpret("concern", "dandruff") == "dandruff"

    def test_long_answer_truncated(self):
        result = interpret("concern", "x" * 300)
        assert result is not None and len(result) <= 80

    def test_empty_returns_none(self):
        assert interpret("concern", "") is None


class TestNextMissing:
    def test_returns_first_unfilled(self):
        item = _next_missing(DEFAULT_INTAKE, {"hair_type": "dry"})
        assert item["slot"] == "concern"

    def test_no_preference_counts_as_filled(self):
        """The whole point: NO_PREFERENCE must satisfy the slot."""
        known = {"hair_type": "dry", "concern": "dandruff", "budget": NO_PREFERENCE}
        assert _next_missing(DEFAULT_INTAKE, known) is None

    def test_all_filled(self):
        known = {"hair_type": "dry", "concern": "dandruff", "budget": "500"}
        assert _next_missing(DEFAULT_INTAKE, known) is None

    def test_intake_terminates_within_slot_count(self):
        """Simulate the failing conversation: it must end, not loop."""
        known: dict = {}
        for _ in range(len(DEFAULT_INTAKE) + 2):
            missing = _next_missing(DEFAULT_INTAKE, known)
            if missing is None:
                break
            value = _interpret_answer(missing["slot"], "no", "no")
            assert value is not None
            known[missing["slot"]] = value
        assert _next_missing(DEFAULT_INTAKE, known) is None
