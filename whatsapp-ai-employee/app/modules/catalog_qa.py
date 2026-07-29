"""Catalog Q&A — the module that answers product and policy questions.

Design rule this file implements: **cache facts, not conversations.**

Retrieval (price, stock, policy text) is cheap and deterministic. Composition —
deciding whether to also suggest the matching conditioner, or nudge toward the
larger size — is sales judgement and stays with the LLM on the Pro plan.

A Basic-plan tenant gets the retrieved facts in a template. A Pro-plan tenant
gets the same facts turned into a reply that sells.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Tenant
from app.modules import retrieval
from app.pipeline.guardrails import CLAIMS_SYSTEM_RULES, sanitize_outbound
from app.services.llm_service import llm_service

log = get_logger("catalog_qa")


@dataclass
class QAResult:
    answer: str | None
    handled_by: str
    cacheable: bool = False
    escalate_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


# Questions that are pure fact lookups — safe to cache and to answer from a
# template even on Pro, because there is no selling decision involved.
FACTUAL_MARKERS = (
    "delivery charge", "shipping charge", "do you ship", "return policy",
    "exchange policy", "how many days", "timing", "open", "cod available",
    "cash on delivery available", "gst", "invoice",
)

# Never fast-path these: they are the conversations where advice earns money.
ADVISORY_MARKERS = (
    "which", "better", "best", "suggest", "recommend", "should i", "suitable",
    "good for", "vs", "or ", "compare", "difference between", "help me choose",
)


def is_advisory(normalized: str) -> bool:
    return any(m in normalized for m in ADVISORY_MARKERS)


def is_factual(normalized: str) -> bool:
    return any(m in normalized for m in FACTUAL_MARKERS)


def _templated_product_reply(
    hits: list[retrieval.ProductHit], currency: str
) -> str:
    if len(hits) == 1:
        h = hits[0]
        size = f" ({h.size})" if h.size else ""
        if h.stock > 0:
            return (
                f"{h.name}{size} is {currency} {h.price:.0f} and is in stock. "
                "Would you like to order it?"
            )
        return (
            f"{h.name}{size} is {currency} {h.price:.0f}, but it is out of stock "
            "right now. I can let our team know you are waiting for it."
        )

    lines = [h.as_line(currency) for h in hits[:4]]
    return "Here is what we have:\n" + "\n".join(f"• {line}" for line in lines)


async def _compose(
    tenant: Tenant,
    question: str,
    facts: str,
    history: list[dict],
) -> QAResult:
    """One cheap LLM call: turn retrieved facts into a reply that also sells."""
    settings_dict = tenant.settings or {}
    tone = settings_dict.get("tone", "warm, brief, helpful")
    business = settings_dict.get("business_name", tenant.name)

    system = (
        f"You are the sales assistant for {business}, a hair care shop, "
        f"replying on WhatsApp. Tone: {tone}.\n\n"
        "GROUNDING RULES:\n"
        "- Answer ONLY from the FACTS block. Never invent products, prices, "
        "sizes, ingredients or stock.\n"
        "- If the FACTS block does not contain the answer, say you will check "
        "with the team. Do not guess.\n"
        "- Keep it under 60 words. WhatsApp, not email.\n"
        "- You may suggest a relevant product from the FACTS block as an add-on "
        "when it genuinely fits, then invite the next step.\n"
        "- Never use markdown headings or bullet symbols other than a dash.\n\n"
        + CLAIMS_SYSTEM_RULES
    )

    history_text = ""
    if history:
        turns = [f"Customer: {t.get('user','')}\nYou: {t.get('bot','')}" for t in history[-3:]]
        history_text = "Recent conversation:\n" + "\n".join(turns) + "\n\n"

    prompt = f"{history_text}FACTS:\n{facts}\n\nCustomer question: {question}"

    try:
        result = await llm_service.generate(system, prompt, temperature=0.3)
    except Exception as exc:  # noqa: BLE001
        log.error({"event": "compose_failed", "error": str(exc)})
        return QAResult(answer=None, handled_by="catalog_qa", escalate_reason="low_confidence")

    safe_text, violations = sanitize_outbound(result.text)
    if violations:
        log.warning({"event": "claim_blocked", "violations": violations})

    return QAResult(
        answer=safe_text or None,
        handled_by="catalog_qa_llm",
        cacheable=False,  # composed sales replies are never cached
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


async def handle(
    db: AsyncSession,
    tenant: Tenant,
    *,
    raw_message: str,
    normalized: str,
    search_query: str,
    history: list[dict],
    metrics,
) -> QAResult:
    currency = tenant.currency or "INR"
    advisory = is_advisory(normalized)
    metrics.mark("advisory", advisory)

    # --- step 1: cheap keyword search (no API calls) ---
    faq_hits = await retrieval.search_faqs(db, str(tenant.id), search_query)
    product_hits = await retrieval.search_products(db, str(tenant.id), search_query)

    top_faq_rank = faq_hits[0].rank if faq_hits else 0.0
    metrics.mark("fts_faq_rank", round(top_faq_rank, 4))
    metrics.mark("fts_products", len(product_hits))

    # FAQ fast path: only for factual, non-advisory questions.
    if (
        faq_hits
        and top_faq_rank >= settings.FTS_FAST_PATH_RANK
        and not advisory
    ):
        metrics.mark("path", "faq_fast_path")
        return QAResult(
            answer=faq_hits[0].answer,
            handled_by="faq_fast_path",
            cacheable=True,
        )

    # Basic plan: templated only, escalate when unsure.
    if not tenant.is_pro:
        if product_hits and not advisory:
            metrics.mark("path", "basic_template")
            return QAResult(
                answer=_templated_product_reply(product_hits, currency),
                handled_by="catalog_template",
                cacheable=True,
            )
        metrics.mark("path", "basic_escalate")
        return QAResult(
            answer=None, handled_by="catalog_qa", escalate_reason="low_confidence"
        )

    # --- step 2: assemble grounded facts for composition (Pro) ---
    fact_blocks: list[str] = []
    if product_hits:
        fact_blocks.append(
            "Products:\n"
            + "\n".join(
                f"- {h.name}"
                + (f" ({h.size})" if h.size else "")
                + f": {currency} {h.price:.0f}, "
                + ("in stock" if h.stock > 0 else "out of stock")
                + (f". {h.description}" if h.description else "")
                + (f" Attributes: {h.attributes}" if h.attributes else "")
                for h in product_hits[:5]
            )
        )
    if faq_hits:
        fact_blocks.append(
            "Store info:\n" + "\n".join(f"- {h.question} {h.answer}" for h in faq_hits[:3])
        )

    # --- step 3: vectors only if keyword search found nothing ---
    if not fact_blocks:
        chunks = await retrieval.semantic_search(str(tenant.id), search_query)
        metrics.mark("semantic_chunks", len(chunks))
        if chunks:
            fact_blocks.append("Reference information:\n" + "\n".join(f"- {c}" for c in chunks))

    if not fact_blocks:
        # Nothing in the tenant's own data matches. Grounded means we do not
        # improvise an answer from general knowledge — we escalate.
        metrics.mark("path", "no_grounding")
        return QAResult(
            answer=None, handled_by="catalog_qa", escalate_reason="low_confidence"
        )

    metrics.mark("path", "compose")
    return await _compose(tenant, raw_message, "\n\n".join(fact_blocks), history)
