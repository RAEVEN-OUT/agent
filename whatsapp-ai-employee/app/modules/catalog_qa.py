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
from app.pipeline.text_signals import is_advisory, is_factual
from app.services.llm_service import llm_service

log = get_logger("catalog_qa")

# Re-exported for backwards compatibility; the definitions live in text_signals
# so the deterministic classifier can use them without importing this module.
__all__ = ["handle", "try_fast_path", "is_advisory", "is_factual", "QAResult"]


@dataclass
class QAResult:
    answer: str | None
    handled_by: str
    cacheable: bool = False
    escalate_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


DEFAULT_CTA = "Would you like to place an order?"


def append_cta(answer: str, cta: str | None = None) -> str:
    """Every terminal reply should carry exactly one forward action.

    A bot that only answers ends conversations; a bot that answers and then
    advances closes sales. This is deterministic and free, so even zero-cost
    fast-path answers keep the sales motion instead of dead-ending.
    """
    if not answer:
        return answer
    text = answer.rstrip()
    if text.endswith("?"):  # already ends in a question — don't stack two
        return text
    return f"{text}\n\n{cta or DEFAULT_CTA}"


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


async def try_fast_path(
    db: AsyncSession,
    tenant: Tenant,
    *,
    normalized: str,
    search_query: str,
    metrics,
) -> QAResult | None:
    """Zero-LLM attempt, run BEFORE the router.

    This is the whole point of the cascade: a question like "what are the
    delivery charges" must never cost a model call. Routing first would defeat
    that, so this probe happens first.

    Deliberately conservative — returns None unless a factual question matches
    an FAQ strongly. Advisory questions are excluded outright, because that is
    where sales judgement lives.
    """
    if is_advisory(normalized):
        metrics.mark("fast_path_skipped", "advisory")
        return None

    faq_hits = await retrieval.search_faqs(db, str(tenant.id), search_query)
    if not faq_hits:
        return None

    top = faq_hits[0]
    metrics.mark("fast_path_faq_rank", round(top.rank, 4))

    # Arbitration: an FAQ must not hijack a product question.
    # "do you have shampoo" lexically matches the FAQ "are the products sulphate
    # free" (its answer contains the word "shampoos"), which would answer a
    # stock question with a chemistry fact. If a product matches at least as
    # well, this is a product question — hand it to the full path.
    product_hits = await retrieval.search_products(db, str(tenant.id), search_query, limit=1)
    if product_hits:
        metrics.mark("fast_path_product_rank", round(product_hits[0].rank, 4))
        if product_hits[0].rank >= top.rank:
            metrics.mark("fast_path_skipped", "product_matched_stronger")
            return None

    if top.rank >= settings.FTS_FAST_PATH_RANK:
        metrics.mark("path", "faq_fast_path_prerouter")
        cta = (tenant.settings or {}).get("cta")
        return QAResult(
            answer=append_cta(top.answer, cta),
            handled_by="faq_fast_path",
            cacheable=True,
        )
    return None


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

    # Basic plan: accurate retrieval, templated delivery, escalate when unsure.
    if not tenant.is_pro:
        if product_hits and not advisory:
            metrics.mark("path", "basic_template")
            return QAResult(
                answer=_templated_product_reply(product_hits, currency),
                handled_by="catalog_template",
                cacheable=True,
            )

        # Keyword search missed. Try semantics before giving up — "how long for
        # shipping?" will not lexically match an FAQ titled "How long does
        # delivery take?", and escalating that to a human is a poor outcome when
        # the answer is sitting in the tenant's own data.
        if not advisory:
            faq_chunks = await retrieval.semantic_search_chunks(
                str(tenant.id), search_query, limit=2, source_type="faq"
            )
            metrics.mark("basic_semantic_hits", len(faq_chunks))
            if faq_chunks:
                answer = faq_chunks[0].metadata.get("answer")
                if answer:
                    metrics.mark("path", "basic_semantic_faq")
                    return QAResult(
                        answer=answer, handled_by="faq_semantic", cacheable=True
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
    result = await _compose(tenant, raw_message, "\n\n".join(fact_blocks), history)

    # Composition failed (quota exhausted, empty model response). We already
    # have real facts in hand — answer from a template rather than escalating a
    # question we can actually answer.
    if not result.answer and product_hits:
        metrics.mark("path", "compose_failed_template_fallback")
        return QAResult(
            answer=_templated_product_reply(product_hits, currency),
            handled_by="catalog_template_degraded",
            cacheable=False,
        )
    if not result.answer and faq_hits:
        metrics.mark("path", "compose_failed_faq_fallback")
        return QAResult(
            answer=faq_hits[0].answer,
            handled_by="faq_degraded",
            cacheable=False,
        )
    return result
