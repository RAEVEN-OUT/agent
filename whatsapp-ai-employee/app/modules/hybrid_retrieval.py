"""Retrieval with an explicit confidence signal.

## Why this replaces keyword-first ordering

Embedding a message costs about $0.000002. Hand-tuned `ts_rank` thresholds were
never worth the accuracy they cost — they produced the "trashy FAQ hits", the
wrong product variant, and the FAQ hijacking. Cost was the wrong reason to put
lexical search first.

## What lexical search is still for

Not recall — *precision on exact values*. Embeddings cannot reliably distinguish:

    "ARG-OIL-100"  vs  "ARG-OIL-200"
    "100 ml"       vs  "200 ml"
    "ORD2607308JWX" (an order number)

Those embed almost identically (cosine > 0.95), which is exactly how a customer
asking for the 200ml gets quoted the 100ml. So lexical search runs **in parallel**
as an exact-token guard, and semantic similarity drives ranking.

It also keeps the bot answering when the embedding provider is rate-limited —
which has already happened once in testing.

## The decision variable

Not "did a keyword match?" but **retrieval confidence**, from two signals the
reference chatbot used and which are stable across queries in a way ts_rank is
not:

    absolute top score   - is anything actually relevant?
    gap to second place  - is the best match clearly the best?

A high score with a tiny gap means several documents fit equally well: that is
ambiguity, and the right response is to ask, not to guess.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Tenant
from app.modules import retrieval
from app.services.llm_service import llm_service
from app.services.qdrant_service import qdrant_service

log = get_logger("hybrid_retrieval")


class Confidence(str, Enum):
    EXACT = "exact"      # an exact identifier matched — answer directly
    HIGH = "high"        # one clear winner — answer from it
    AMBIGUOUS = "ambiguous"  # several equally good — ask which
    LOW = "low"          # weak but present — let the LLM compose carefully
    NONE = "none"        # nothing relevant — escalate, never improvise


@dataclass
class Hit:
    kind: str          # "product" | "faq"
    ref: str           # sku or faq id
    title: str
    text: str
    score: float
    exact: bool = False
    payload: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    hits: list[Hit] = field(default_factory=list)
    confidence: Confidence = Confidence.NONE
    top_score: float = 0.0
    gap: float = 0.0
    used_semantic: bool = False
    used_lexical: bool = False
    exact_terms: list[str] = field(default_factory=list)

    @property
    def top(self) -> Hit | None:
        return self.hits[0] if self.hits else None

    def facts_block(self, currency: str = "INR", limit: int = 5) -> str:
        """Grounding text handed to the LLM. Only retrieved content, never priors."""
        lines = []
        for hit in self.hits[:limit]:
            if hit.kind == "product":
                p = hit.payload
                size = f" ({p.get('size')})" if p.get("size") else ""
                price = p.get("price")
                # A hit may arrive from the vector store, whose payload carries no
                # price. Never format None, and never guess a number.
                price_text = (
                    f"{currency} {float(price):.0f}" if price is not None else "price on request"
                )
                stock_value = p.get("stock")
                stock = (
                    ("in stock" if stock_value > 0 else "out of stock")
                    if isinstance(stock_value, int)
                    else "stock unknown"
                )
                lines.append(
                    f"- PRODUCT {p.get('name') or hit.title}{size}: {price_text}, "
                    f"{stock}. {p.get('description') or ''}".strip()
                )
            else:
                lines.append(f"- INFO {hit.title} {hit.text}")
        return "\n".join(lines)

    def as_trace(self) -> dict:
        return {
            "confidence": self.confidence.value,
            "top_score": round(self.top_score, 4),
            "gap": round(self.gap, 4),
            "hits": len(self.hits),
            "semantic": self.used_semantic,
            "lexical": self.used_lexical,
            "exact": self.exact_terms,
        }


# --- exact-identifier detection ------------------------------------------

_SIZE_RE = re.compile(r"\b(\d{2,4})\s*(ml|g|gm|gms|kg|l)\b", re.I)
_SKU_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+){1,3})\b")
_ORDER_RE = re.compile(r"\bORD[0-9A-Z]{6,}\b", re.I)


def find_exact_terms(text: str) -> list[str]:
    """Tokens where an approximate match is a wrong answer, not a near miss."""
    terms: list[str] = []
    for match in _SIZE_RE.finditer(text or ""):
        terms.append(f"{match.group(1)} {match.group(2).lower()}")
    terms += [m.group(1) for m in _SKU_RE.finditer((text or "").upper())]
    terms += [m.group(0).upper() for m in _ORDER_RE.finditer(text or "")]
    return list(dict.fromkeys(terms))


def _classify(top: float, gap: float, has_exact: bool) -> Confidence:
    if has_exact:
        return Confidence.EXACT
    if top < settings.RETRIEVAL_FLOOR:
        return Confidence.NONE
    if top >= settings.RETRIEVAL_HIGH and gap >= settings.RETRIEVAL_MIN_GAP:
        return Confidence.HIGH
    if top >= settings.RETRIEVAL_HIGH:
        # Several documents fit equally well. Asking beats guessing.
        return Confidence.AMBIGUOUS
    return Confidence.LOW


async def retrieve(
    db: AsyncSession,
    tenant: Tenant,
    query: str,
    *,
    limit: int = 5,
    metrics=None,
) -> RetrievalResult:
    """Semantic-primary, lexical exact-guard, merged and scored."""
    result = RetrievalResult()
    tenant_id = str(tenant.id)
    if not query or not query.strip():
        return result

    exact_terms = find_exact_terms(query)
    result.exact_terms = exact_terms

    # --- semantic: the primary recall mechanism ---
    semantic_hits: list[Hit] = []
    if llm_service.available:
        try:
            vector = await llm_service.embed(query)
            chunks = await qdrant_service.search(tenant_id, vector, limit=limit + 3)
            result.used_semantic = True
            for chunk in chunks:
                payload = chunk.metadata or {}
                kind = "product" if payload.get("source_type") == "product" else "faq"
                semantic_hits.append(
                    Hit(
                        kind=kind,
                        ref=str(payload.get("source_id") or chunk.id),
                        title=str(payload.get("name") or payload.get("question") or ""),
                        text=chunk.text,
                        score=float(chunk.score),
                        payload=payload,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            log.warning({"event": "semantic_unavailable", "error": str(exc)[:200]})

    # --- lexical: exact-value guard + fallback when semantics are unavailable ---
    lexical_hits: list[Hit] = []
    try:
        products = await retrieval.search_products(db, tenant_id, query, limit=limit)
        faqs = await retrieval.search_faqs(db, tenant_id, query, limit=3)
        result.used_lexical = True

        for p in products:
            haystack = f"{p.name} {p.size or ''} {p.sku}".lower()
            is_exact = any(t.lower() in haystack for t in exact_terms)
            lexical_hits.append(
                Hit(
                    kind="product",
                    ref=p.sku,
                    title=p.name,
                    text=f"{p.name} {p.description}",
                    # Lexical rank is not comparable to cosine similarity, so it
                    # is mapped into a conservative band. Exact matches are
                    # promoted above everything, which is the whole point.
                    score=0.99 if is_exact else min(0.60, 0.35 + p.rank),
                    exact=is_exact,
                    payload={
                        "name": p.name, "size": p.size, "price": p.price,
                        "stock": p.stock, "description": p.description, "sku": p.sku,
                    },
                )
            )
        for f in faqs:
            lexical_hits.append(
                Hit(
                    kind="faq",
                    ref=f.id,
                    title=f.question,
                    text=f.answer,
                    score=min(0.60, 0.35 + f.rank),
                    payload={"question": f.question, "answer": f.answer},
                )
            )
    except Exception as exc:  # noqa: BLE001
        log.error({"event": "lexical_failed", "error": str(exc)[:200]})

    # --- merge, preferring the higher score per reference ---
    merged: dict[str, Hit] = {}
    for hit in semantic_hits + lexical_hits:
        key = f"{hit.kind}:{hit.ref}"
        current = merged.get(key)
        if current is None or hit.score > current.score:
            if current is not None:
                hit.exact = hit.exact or current.exact
                # keep whichever payload is richer
                hit.payload = hit.payload or current.payload
            merged[key] = hit

    hits = sorted(merged.values(), key=lambda h: (h.exact, h.score), reverse=True)
    result.hits = hits[:limit]

    # Hydrate product hits from Postgres. The vector store payload is for
    # *finding* things, never for quoting them: it holds whatever the price was
    # at index time, so serving from it would quote stale prices and stale stock
    # after any catalog edit. Postgres is the only source of truth for money.
    for hit in result.hits:
        if hit.kind != "product":
            continue
        if hit.payload.get("price") is not None and hit.payload.get("stock") is not None:
            continue
        sku = hit.payload.get("sku") or hit.ref
        try:
            live = await retrieval.get_product_by_sku(db, tenant_id, str(sku))
        except Exception as exc:  # noqa: BLE001
            log.warning({"event": "hydrate_failed", "sku": sku, "error": str(exc)[:120]})
            continue
        if live:
            hit.payload.update(
                {
                    "sku": live.sku, "name": live.name, "size": live.size,
                    "price": live.price, "stock": live.stock,
                    "description": live.description,
                }
            )
            hit.title = live.name
        else:
            # Indexed but no longer in the catalog — drop it rather than offer it.
            hit.payload["stale"] = True

    result.hits = [h for h in result.hits if not h.payload.get("stale")]

    if hits:
        result.top_score = hits[0].score
        result.gap = hits[0].score - (hits[1].score if len(hits) > 1 else 0.0)

    result.confidence = _classify(
        result.top_score, result.gap, any(h.exact for h in result.hits)
    )

    if metrics:
        metrics.mark("retrieval", result.as_trace())

    return result
