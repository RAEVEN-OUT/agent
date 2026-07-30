"""Consultation intake — the "consultant" module.

Same code shape as a bakery's flavour/weight intake or a boutique's
occasion/size intake; only the question set differs. That question set lives in
tenant settings, so a new vertical is a config change, not a new module.
"""

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Customer, Tenant
from app.modules import retrieval
from app.pipeline.guardrails import CLAIMS_SYSTEM_RULES, sanitize_outbound
from app.services.llm_service import llm_service

log = get_logger("consultation")

# Default hair care intake. Override per tenant via settings["intake"].
DEFAULT_INTAKE = [
    {"slot": "hair_type", "question": "Is your hair oily, dry, normal or a mix?"},
    {"slot": "concern", "question": "What would you like to work on — hair fall, dandruff, frizz, dryness or growth?"},
    {"slot": "budget", "question": "Any budget you'd like me to stay within?"},
]


@dataclass
class ConsultResult:
    answer: str | None
    handled_by: str
    state_update: dict
    profile_update: dict
    escalate_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def _intake_spec(tenant: Tenant) -> list[dict]:
    spec = (tenant.settings or {}).get("intake")
    if isinstance(spec, list) and spec:
        return spec
    return DEFAULT_INTAKE


def _next_missing(spec: list[dict], known: dict) -> dict | None:
    for item in spec:
        if not known.get(item["slot"]):
            return item
    return None


# "no", "none", "any" are legitimate answers meaning "no preference". Treating
# them as an empty slot makes the bot re-ask the same question forever — which
# is exactly what happened in testing.
DECLINE_WORDS = {
    "no", "none", "nope", "any", "anything", "no preference", "doesnt matter",
    "does not matter", "not sure", "dont know", "do not know", "skip", "na",
    "no budget", "not really", "whatever", "up to you", "you decide",
}

NO_PREFERENCE = "any"


def _interpret_answer(slot: str, raw_message: str, normalized: str) -> str | None:
    """Read this message as the answer to the question we just asked.

    Always returns something for non-empty input. An intake that cannot accept
    an answer is worse than one that accepts a slightly wrong one — the customer
    can correct a wrong value, but cannot escape a loop.
    """
    text = (normalized or "").strip()
    if not text:
        return None

    stripped = re.sub(r"[^\w\s]", "", text).strip()
    if stripped in DECLINE_WORDS or any(
        stripped.startswith(f"{word} ") for word in ("no ", "any ", "not ")
    ):
        return NO_PREFERENCE

    if slot == "budget":
        match = re.search(r"(\d[\d,]{1,7})", text.replace(",", ""))
        if match:
            return match.group(1)
        return NO_PREFERENCE  # they said something non-numeric; stop asking

    return raw_message.strip()[:80]


async def handle(
    db: AsyncSession,
    tenant: Tenant,
    customer: Customer,
    *,
    raw_message: str,
    normalized: str = "",
    slots: dict,
    state: dict,
    metrics,
) -> ConsultResult:
    if not tenant.is_pro:
        # Consultative selling is the Pro differentiator; Basic hands to human.
        return ConsultResult(
            answer=None,
            handled_by="consultation",
            state_update={},
            profile_update={},
            escalate_reason="low_confidence",
        )

    spec = _intake_spec(tenant)

    # Merge what we already know: long-term profile + this flow's state + slots
    # the router just extracted from the message.
    known = {**(customer.profile or {}), **(state.get("consult") or {})}
    for key in ("hair_type", "concern", "budget", "length"):
        if slots.get(key):
            known[key] = slots[key]

    # Interpret this message as the answer to the slot we last asked about.
    # Without this, a slot only ever gets filled if the LLM router happens to
    # extract it — and "none" or "no" extract nothing, so the same question
    # repeats indefinitely.
    awaiting = state.get("consult_awaiting")
    if awaiting and not known.get(awaiting):
        value = _interpret_answer(awaiting, raw_message, normalized)
        if value:
            known[awaiting] = value
            metrics.mark("consult_slot_filled", f"{awaiting}={value}")

    missing = _next_missing(spec, known)
    if missing:
        metrics.mark("path", "consult_question")
        return ConsultResult(
            answer=missing["question"],
            handled_by="consultation_intake",
            state_update={
                "consult": known,
                "consult_awaiting": missing["slot"],
                "flow": "consultation",
            },
            profile_update=known,
        )

    # Profile complete -> recommend from this tenant's catalog only.
    # Search the CONCERN first, on its own. Concern is what the customer asked
    # about ("dandruff"); hair type is a qualifier. Mixing them lets a strong
    # hair-type match outrank the actual problem — which is how "which shampoo
    # for dandruff" ended up recommending a dry-hair oil.
    concern = str(known.get("concern") or "").strip()
    hair_type = str(known.get("hair_type") or "").strip()

    products: list = []
    if concern and concern != NO_PREFERENCE:
        products = await retrieval.search_products(db, str(tenant.id), concern, limit=6)
        metrics.mark("consult_concern_hits", len(products))

    if not products:
        combined = " ".join(t for t in (concern, hair_type) if t and t != NO_PREFERENCE)
        if combined:
            products = await retrieval.search_products(db, str(tenant.id), combined, limit=6)

    if not products:
        products = await retrieval.search_products(db, str(tenant.id), "hair", limit=6)

    if not products:
        return ConsultResult(
            answer=None,
            handled_by="consultation",
            state_update={"consult": known},
            profile_update=known,
            escalate_reason="low_confidence",
        )

    budget = known.get("budget")
    if budget and budget != NO_PREFERENCE:
        try:
            limit_value = float(str(budget).replace(",", ""))
            in_budget = [p for p in products if p.price <= limit_value * 1.15]
            products = in_budget or products
        except (TypeError, ValueError):
            pass

    currency = tenant.currency or "INR"
    facts = "\n".join(
        f"- {p.name}" + (f" ({p.size})" if p.size else "")
        + f": {currency} {p.price:.0f}, "
        + ("in stock" if p.stock > 0 else "out of stock")
        + (f". {p.description}" if p.description else "")
        for p in products[:5]
    )

    system = (
        f"You are a hair care advisor for {tenant.name} on WhatsApp.\n"
        "Recommend a routine of 1-3 products from the FACTS list only.\n"
        "Explain in one short line why each suits this customer.\n"
        "Never invent products, prices or ingredients. Under 80 words.\n"
        "Address the customer's stated CONCERN first — it matters more than "
        "their hair type.\n"
        "Do not greet them again; you are mid-conversation.\n"
        "End by asking if they'd like to order.\n\n" + CLAIMS_SYSTEM_RULES
    )
    prompt = (
        f"Customer profile: {known}\n\nFACTS (available products):\n{facts}\n\n"
        f"Customer's latest message: {raw_message}"
    )

    try:
        result = await llm_service.generate(system, prompt, temperature=0.35, max_output_tokens=350)
    except Exception as exc:  # noqa: BLE001
        log.error({"event": "consult_compose_failed", "error": str(exc)})
        return ConsultResult(
            answer=None,
            handled_by="consultation",
            state_update={"consult": known},
            profile_update=known,
            escalate_reason="low_confidence",
        )

    safe_text, violations = sanitize_outbound(result.text)
    if violations:
        log.warning({"event": "claim_blocked", "module": "consultation", "violations": violations})

    metrics.mark("path", "consult_recommend")
    return ConsultResult(
        answer=safe_text,
        handled_by="consultation_recommend",
        state_update={"consult": known, "consult_awaiting": None, "flow": None},
        profile_update=known,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
