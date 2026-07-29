"""Consultation intake — the "consultant" module.

Same code shape as a bakery's flavour/weight intake or a boutique's
occasion/size intake; only the question set differs. That question set lives in
tenant settings, so a new vertical is a config change, not a new module.
"""

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


async def handle(
    db: AsyncSession,
    tenant: Tenant,
    customer: Customer,
    *,
    raw_message: str,
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

    missing = _next_missing(spec, known)
    if missing:
        metrics.mark("path", "consult_question")
        return ConsultResult(
            answer=missing["question"],
            handled_by="consultation_intake",
            state_update={"consult": known, "flow": "consultation"},
            profile_update=known,
        )

    # Profile complete -> recommend from this tenant's catalog only.
    search_terms = " ".join(
        str(known.get(k, "")) for k in ("concern", "hair_type") if known.get(k)
    )
    products = await retrieval.search_products(db, str(tenant.id), search_terms, limit=6)
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
    if budget:
        try:
            limit_value = float(budget)
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
        state_update={"consult": known, "flow": None},
        profile_update=known,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
