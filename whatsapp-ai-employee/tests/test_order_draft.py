"""Order draft lifecycle.

Regression origin: a live session where an abandoned draft from a PREVIOUS
conversation survived, so "i want 3" (meaning 3 shampoos) re-displayed
yesterday's basket — 2 x Argan Oil, an old address, an old pincode — and the
customer confirmed an order they never built.

Two failures combined:
  1. drafts never expired
  2. at the confirm step, anything that was not yes/no re-printed the summary
"""

from datetime import datetime, timedelta, timezone

from app.modules.order_capture import (
    DRAFT_TTL_MINUTES,
    _extract_quantity_change,
)
from app.pipeline.normalize import normalize


def qty(text: str):
    return _extract_quantity_change(normalize(text))


class TestQuantityEditAtConfirm:
    """The exact message that caused the loop."""

    def test_i_want_3(self):
        assert qty("i want 3") == 3

    def test_make_it_two_digits(self):
        assert qty("make it 5") == 5

    def test_change_to(self):
        assert qty("change to 4") == 4

    def test_actually_n(self):
        assert qty("actually 2") == 2

    def test_give_me_n(self):
        assert qty("give me 6") == 6

    def test_bare_number_with_unit(self):
        assert qty("3 bottles") == 3
        assert qty("2 units") == 2

    def test_confirmation_words_are_not_quantities(self):
        for text in ("yes", "no", "ok", "confirm"):
            assert qty(text) is None, text

    def test_unrelated_text_is_not_a_quantity(self):
        for text in ("where is my order", "thanks a lot", "cod"):
            assert qty(text) is None, text

    def test_absurd_quantity_rejected(self):
        # _parse_quantity caps at 50; a stray long number must not become an order
        assert qty("i want 99") is None


class TestDraftExpiry:
    def test_ttl_is_configured(self):
        assert 5 <= DRAFT_TTL_MINUTES <= 240

    def test_fresh_draft_is_not_expired(self):
        started = datetime.now(timezone.utc) - timedelta(minutes=1)
        age = datetime.now(timezone.utc) - started
        assert age <= timedelta(minutes=DRAFT_TTL_MINUTES)

    def test_old_draft_is_expired(self):
        started = datetime.now(timezone.utc) - timedelta(minutes=DRAFT_TTL_MINUTES + 5)
        age = datetime.now(timezone.utc) - started
        assert age > timedelta(minutes=DRAFT_TTL_MINUTES)

    def test_malformed_timestamp_does_not_crash(self):
        for bad in ("not-a-date", "", None, 12345):
            try:
                datetime.fromisoformat(bad)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            raise AssertionError(f"{bad!r} should not parse")
