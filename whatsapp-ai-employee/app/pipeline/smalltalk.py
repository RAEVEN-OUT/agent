import re

# Zero-cost path. These messages carry no sales judgement, so a canned reply
# is the correct behaviour, not a compromise.
GENERIC_INTENTS: dict[str, list[str]] = {
    "greeting": [
        "hi", "hello", "hey", "helo", "hii", "hiya", "good morning",
        "good evening", "good afternoon", "namaste", "hi there",
    ],
    "goodbye": ["bye", "goodbye", "see you", "cya", "ok bye", "thank you bye"],
    "thanks": [
        "thanks", "thank you", "thanku", "thankyou", "tq", "appreciate it",
        "thanks a lot", "thank you so much",
    ],
    "bot_identity": [
        "who are you", "what are you", "what is your name", "are you a bot",
        "are you human", "is this a bot", "who is this",
    ],
    "capabilities": [
        "what can you do", "how can you help", "what do you do",
    ],
}

HUMAN_KEYWORDS = (
    "talk to human", "talk to a human", "speak to human", "real person",
    "live agent", "customer care", "customer service", "call me",
    "talk to owner", "speak to someone",
)


def detect_smalltalk(normalized: str) -> str | None:
    """Exact-ish match only. Deliberately conservative.

    Anything ambiguous must fall through to the real pipeline — a false
    positive here means a canned reply to a genuine sales question.
    """
    clean = re.sub(r"[^\w\s]", "", normalized).strip()
    if not clean:
        return None

    for intent, phrases in GENERIC_INTENTS.items():
        if clean in phrases:
            return intent

    if any(k in clean for k in HUMAN_KEYWORDS):
        return "human_request"
    return None


def canned_reply(intent: str, tenant_settings: dict) -> str | None:
    bot_name = tenant_settings.get("bot_name", "our assistant")
    business = tenant_settings.get("business_name", "our store")

    replies = {
        "greeting": tenant_settings.get(
            "welcome_message",
            f"Hi! Welcome to {business}. How can I help you today?",
        ),
        "goodbye": tenant_settings.get(
            "farewell_message", "Thank you! Message us anytime."
        ),
        "thanks": "Happy to help! Anything else you would like to know?",
        "bot_identity": (
            f"I am {bot_name}, the assistant for {business}. "
            "I can help with products, orders and delivery."
        ),
        "capabilities": tenant_settings.get(
            "capabilities_message",
            "I can help you choose a product, place an order, "
            "check your order status, and answer questions about delivery and returns.",
        ),
        "human_request": tenant_settings.get(
            "human_request_message",
            "Sure — I am connecting you to our team. Someone will reply here shortly.",
        ),
    }
    return replies.get(intent)
