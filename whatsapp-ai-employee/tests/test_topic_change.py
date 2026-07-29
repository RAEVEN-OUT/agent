"""Mid-flow router skipping.

Six order slots means six router calls per order if we route every reply. A bare
"641002" is an answer, not a new intent — skipping the router there is the single
biggest per-order cost saving. But a misfire shoves a real question into an
address field, so the detector is deliberately biased toward "this is a question".
"""

from app.pipeline.normalize import looks_like_topic_change, normalize


class TestSlotAnswers:
    """These must NOT be treated as topic changes (skip the router, save money)."""

    def test_pincode(self):
        assert not looks_like_topic_change(normalize("641002"))

    def test_quantity(self):
        assert not looks_like_topic_change(normalize("2"))

    def test_name(self):
        assert not looks_like_topic_change(normalize("Aparna"))

    def test_address(self):
        assert not looks_like_topic_change(
            normalize("12 Gandhi Street, RS Puram, Coimbatore")
        )

    def test_payment_method(self):
        assert not looks_like_topic_change(normalize("cod"))
        assert not looks_like_topic_change(normalize("upi"))

    def test_simple_confirmation(self):
        assert not looks_like_topic_change(normalize("yes"))
        assert not looks_like_topic_change(normalize("ok"))


class TestTopicChanges:
    """These MUST be treated as new questions (pay for the router)."""

    def test_explicit_question(self):
        assert looks_like_topic_change(normalize("how much is the 200ml?"))

    def test_actually_prefix(self):
        assert looks_like_topic_change(normalize("actually make it the tea tree one"))

    def test_cancel(self):
        assert looks_like_topic_change(normalize("cancel my order"))

    def test_wait(self):
        assert looks_like_topic_change(normalize("wait"))

    def test_question_word_start(self):
        for text in (
            "what is the price",
            "which one is bigger",
            "do you have conditioner",
            "can you add the oil too",
        ):
            assert looks_like_topic_change(normalize(text)), text

    def test_asks_for_different_product(self):
        assert looks_like_topic_change(normalize("another shampoo instead"))

    def test_bare_question_mark(self):
        assert looks_like_topic_change(normalize("cod?"))


class TestEmpty:
    def test_empty_is_not_a_topic_change(self):
        assert not looks_like_topic_change("")
