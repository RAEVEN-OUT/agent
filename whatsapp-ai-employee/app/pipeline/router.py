"""LLM intent router (Pro plan).

One cheap model call decides which module handles the message, based on the
conversation's actual state rather than a fixed script. That is what allows
add-ons before the close, after the close, or not at all — the flow is decided
per message, not pre-drawn.
"""

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.core.retry import is_rate_limit_error
from app.services.llm_service import LLMResult, llm_service

log = get_logger("router")

INTENTS = (
    "catalog_qa",      # price / availability / ingredients / policy questions
    "consultation",    # wants a recommendation, needs profiling first
    "order_capture",   # ready to buy, or mid-way through giving details
    "order_status",    # asking about an existing order
    "payment",         # asking how to pay / payment failed
    "human_request",   # explicitly wants a person
    "smalltalk",       # greeting / thanks / chit-chat
    "other",           # none of the above
)

SYSTEM_PROMPT = (
    "You are the routing layer of a WhatsApp assistant for a hair care shop.\n"
    "Classify the customer's latest message into exactly one intent and extract "
    "any useful slots.\n\n"
    f"Valid intents: {', '.join(INTENTS)}\n\n"
    "Rules:\n"
    "- Use the conversation state: if the customer is mid-order and replies with "
    "an address or quantity, that is order_capture, not catalog_qa.\n"
    "- A question about a specific product's price/size/stock is catalog_qa.\n"
    "- A request for advice ('which is good for dry hair', 'what should I use') "
    "is consultation.\n"
    "- Set confidence below 0.5 when the message is genuinely ambiguous.\n"
    "- Never invent product names.\n\n"
    'Reply with JSON only: {"intent": str, "confidence": float, '
    '"slots": {"product": str|null, "quantity": int|null, "hair_type": str|null, '
    '"concern": str|null, "budget": number|null}}'
)


@dataclass
class RouteDecision:
    intent: str
    confidence: float
    slots: dict = field(default_factory=dict)
    usage: LLMResult | None = None
    # True when the model call itself failed (quota, empty response, bad JSON).
    # The caller must degrade to keyword routing, not escalate every message.
    failed: bool = False
    rate_limited: bool = False


def _build_prompt(message: str, state: dict, history: list[dict], profile: dict) -> str:
    lines = []
    if history:
        lines.append("Recent conversation:")
        for turn in history[-4:]:
            lines.append(f"  Customer: {turn.get('user', '')}")
            lines.append(f"  Assistant: {turn.get('bot', '')}")
    if state:
        lines.append(f"Current flow state: {state}")
    if profile:
        lines.append(f"Known customer profile: {profile}")
    lines.append(f"Latest customer message: {message}")
    return "\n".join(lines)


async def route(
    message: str,
    *,
    state: dict | None = None,
    history: list[dict] | None = None,
    profile: dict | None = None,
) -> RouteDecision:
    prompt = _build_prompt(message, state or {}, history or [], profile or {})

    try:
        data, usage = await llm_service.generate_json(SYSTEM_PROMPT, prompt)
    except Exception as exc:  # noqa: BLE001
        limited = is_rate_limit_error(exc)
        log.error(
            {
                "event": "router_failed",
                "reason": "rate_limited" if limited else "error",
                "error": str(exc)[:300],
            }
        )
        return RouteDecision(
            intent="other", confidence=0.0, failed=True, rate_limited=limited
        )

    if not data:
        # Call succeeded but produced nothing parseable (usually a thinking
        # model that spent its output budget). Degrade, don't escalate.
        log.warning(
            {
                "event": "router_unparseable",
                "finish_reason": usage.finish_reason,
                "raw": (usage.text or "")[:200],
            }
        )
        return RouteDecision(
            intent="other", confidence=0.0, usage=usage, failed=True
        )

    intent = str(data.get("intent", "other")).strip()
    if intent not in INTENTS:
        intent = "other"

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    slots = data.get("slots") or {}
    if not isinstance(slots, dict):
        slots = {}
    slots = {k: v for k, v in slots.items() if v not in (None, "", "null")}

    return RouteDecision(
        intent=intent, confidence=max(0.0, min(confidence, 1.0)), slots=slots, usage=usage
    )
