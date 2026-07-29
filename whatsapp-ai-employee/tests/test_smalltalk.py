from app.pipeline.normalize import normalize
from app.pipeline.smalltalk import canned_reply, detect_smalltalk

SETTINGS = {
    "business_name": "Glow Roots",
    "bot_name": "Roo",
    "welcome_message": "Hi! Welcome to Glow Roots.",
}


class TestDetectSmalltalk:
    def test_greetings(self):
        for text in ("hi", "hello", "hey", "good morning", "Hii"):
            assert detect_smalltalk(normalize(text)) == "greeting"

    def test_thanks(self):
        assert detect_smalltalk(normalize("thanks")) == "thanks"
        assert detect_smalltalk(normalize("thank you so much")) == "thanks"

    def test_bot_identity(self):
        assert detect_smalltalk(normalize("are you a bot")) == "bot_identity"

    def test_human_request(self):
        assert detect_smalltalk(normalize("i want to talk to a human")) == "human_request"
        assert detect_smalltalk(normalize("customer care please")) == "human_request"

    def test_real_questions_fall_through(self):
        """The critical test: a sales question must never be treated as small talk."""
        for text in (
            "how much is the argan oil",
            "hi do you have rosemary shampoo",
            "hello is this available in 200ml",
            "which one is good for dandruff",
            "i want to order",
        ):
            assert detect_smalltalk(normalize(text)) is None, text

    def test_empty(self):
        assert detect_smalltalk("") is None


class TestCannedReply:
    def test_uses_tenant_welcome_message(self):
        assert canned_reply("greeting", SETTINGS) == "Hi! Welcome to Glow Roots."

    def test_falls_back_to_default_when_unset(self):
        reply = canned_reply("greeting", {"business_name": "Shop X"})
        assert "Shop X" in reply

    def test_bot_identity_includes_names(self):
        reply = canned_reply("bot_identity", SETTINGS)
        assert "Roo" in reply and "Glow Roots" in reply

    def test_unknown_intent_returns_none(self):
        assert canned_reply("nonsense", SETTINGS) is None
