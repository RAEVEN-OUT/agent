from app.pipeline.normalize import (
    is_meaningless,
    local_rewrite,
    looks_like_followup,
    normalize,
)


class TestNormalize:
    def test_lowercases_and_trims(self):
        assert normalize("  HELLO There  ") == "hello there"

    def test_strips_emoji(self):
        assert "🌿" not in normalize("do you have argan oil 🌿")
        assert normalize("hi 👋") == "hi"

    def test_expands_shorthand(self):
        assert normalize("wht is ur price") == "what is your price"
        assert normalize("is it avl") == "is it available"
        assert normalize("cod?") == "cash on delivery?"

    def test_collapses_repeated_punctuation(self):
        assert normalize("really???") == "really?"

    def test_handles_empty(self):
        assert normalize("") == ""
        assert normalize(None) == ""


class TestIsMeaningless:
    def test_empty_is_meaningless(self):
        assert is_meaningless("")

    def test_emoji_only_is_meaningless(self):
        assert is_meaningless(normalize("👍👍👍"))

    def test_repeated_chars_is_meaningless(self):
        assert is_meaningless("aaaaaa")
        assert is_meaningless("wwwww")

    def test_real_question_is_not_meaningless(self):
        assert not is_meaningless("price of argan oil")

    def test_short_real_word_is_not_meaningless(self):
        # Guards against an over-eager gibberish filter eating real replies.
        assert not is_meaningless("cod")
        assert not is_meaningless("2")


class TestFollowup:
    def test_pronoun_short_message_is_followup(self):
        assert looks_like_followup("is it in stock")

    def test_prefix_is_followup(self):
        assert looks_like_followup("what about the 200ml")

    def test_standalone_question_is_not_followup(self):
        assert not looks_like_followup("do you sell rosemary shampoo for dandruff")

    def test_local_rewrite_prepends_topic(self):
        assert local_rewrite("what about 200ml", "argan hair oil") == (
            "argan hair oil what about 200ml"
        )

    def test_local_rewrite_without_topic_is_noop(self):
        assert local_rewrite("what about 200ml", "") == "what about 200ml"
