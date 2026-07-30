"""Retrieval layer: cheap keyword search first, vectors only when needed.

Order matters for cost. Postgres full-text search costs a few milliseconds and
no API call. The embedding + Qdrant path only runs when keyword search is not
confident, which in practice is the minority of messages.
"""

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_service import llm_service
from app.services.qdrant_service import qdrant_service

log = get_logger("retrieval")

# Attributes MUST be in the searchable document. Without them, a query like
# "dandruff" cannot match the Tea Tree shampoo, because the word only exists in
# attributes.concern — never in the name or description. That silently produces
# confident recommendations of the wrong product.
_PRODUCT_DOC = (
    "coalesce(name,'') || ' ' || coalesce(description,'') || ' ' "
    "|| coalesce(size,'') || ' ' || coalesce(attributes::text,'')"
)

# plainto_tsquery ANDs every term, which is catastrophic for conversational
# input: "how much is argan oil" becomes 'much & argan & oil', and because no
# product contains the word "much" it matches NOTHING. Real customers pad every
# question with filler, so AND semantics means near-total retrieval failure.
#
# We OR the meaningful terms instead and let ts_rank do the discriminating —
# documents matching more terms rank higher, and the threshold filters the rest.
_TOKEN_RE = re.compile(r"[a-z0-9]+")

_FILLER_WORDS = frozenset(
    """
    the a an and or of in on at to for from with is are was were be been am
    do does did done have has had having how what which who whom why when where
    much many more most some any all this that these those there here
    you your yours i me my mine we us our ours it its they them their
    please pls kindly tell show give send need want looking got get
    hi hello hey ok okay yes no not can could would should will shall may
    about like just also very really too so if then than but
    """.split()
)


def build_or_tsquery(text_value: str) -> str:
    """Turn conversational text into an OR tsquery of meaningful terms."""
    tokens = [
        t for t in _TOKEN_RE.findall((text_value or "").lower())
        if len(t) >= 3 and t not in _FILLER_WORDS
    ]
    # dict.fromkeys dedupes while preserving order
    return " | ".join(dict.fromkeys(tokens))


PRODUCT_FTS_SQL = text(
    f"""
    SELECT id::text, sku, name, description, size, price, stock, attributes,
           ts_rank(to_tsvector('english', {_PRODUCT_DOC}),
                   to_tsquery('english', :q)) AS rank
    FROM products
    WHERE tenant_id = :tenant_id
      AND is_active = true
      AND to_tsvector('english', {_PRODUCT_DOC}) @@ to_tsquery('english', :q)
    ORDER BY rank DESC
    LIMIT :limit
    """
)

FAQ_FTS_SQL = text(
    """
    SELECT id::text, question, answer,
           ts_rank(to_tsvector('english', question || ' ' || answer),
                   to_tsquery('english', :q)) AS rank
    FROM faqs
    WHERE tenant_id = :tenant_id
      AND is_active = true
      AND to_tsvector('english', question || ' ' || answer)
          @@ to_tsquery('english', :q)
    ORDER BY rank DESC
    LIMIT :limit
    """
)


@dataclass
class ProductHit:
    id: str
    sku: str
    name: str
    description: str
    size: str | None
    price: float
    stock: int
    attributes: dict
    rank: float

    def as_line(self, currency: str = "INR") -> str:
        size = f" ({self.size})" if self.size else ""
        stock = "in stock" if self.stock > 0 else "out of stock"
        return f"{self.name}{size} - {currency} {self.price:.0f} - {stock}"


@dataclass
class FaqHit:
    id: str
    question: str
    answer: str
    rank: float


async def search_products(
    db: AsyncSession, tenant_id: str, query: str, limit: int = 5
) -> list[ProductHit]:
    tsquery = build_or_tsquery(query)
    if not tsquery:
        return []
    rows = await db.execute(
        PRODUCT_FTS_SQL, {"tenant_id": tenant_id, "q": tsquery, "limit": limit}
    )
    return [
        ProductHit(
            id=r[0],
            sku=r[1],
            name=r[2],
            description=r[3] or "",
            size=r[4],
            price=float(r[5]),
            stock=int(r[6]),
            attributes=r[7] or {},
            rank=float(r[8]),
        )
        for r in rows.all()
    ]


async def search_faqs(
    db: AsyncSession, tenant_id: str, query: str, limit: int = 3
) -> list[FaqHit]:
    tsquery = build_or_tsquery(query)
    if not tsquery:
        return []
    rows = await db.execute(
        FAQ_FTS_SQL, {"tenant_id": tenant_id, "q": tsquery, "limit": limit}
    )
    return [
        FaqHit(id=r[0], question=r[1], answer=r[2], rank=float(r[3])) for r in rows.all()
    ]


async def semantic_search_chunks(
    tenant_id: str, query: str, limit: int = 4, source_type: str | None = None
):
    """Vector search. Available on every plan — an embedding costs ~1/100th of a
    generation call and is cached for a week, so there is no reason to withhold
    accurate retrieval from Basic tenants. Composition is the Pro differentiator,
    not finding the right fact.
    """
    if not llm_service.available:
        return []
    try:
        vector = await llm_service.embed(query)
    except Exception as exc:  # noqa: BLE001
        log.error({"event": "embed_failed", "error": str(exc)})
        return []

    chunks = await qdrant_service.search(
        tenant_id, vector, limit=limit, source_type=source_type
    )
    return [c for c in chunks if c.score >= settings.SEMANTIC_MIN_SCORE]


async def semantic_search(tenant_id: str, query: str, limit: int = 4) -> list[str]:
    """Text-only convenience wrapper for grounded composition."""
    chunks = await semantic_search_chunks(tenant_id, query, limit=limit)
    return [c.text for c in chunks]


async def get_product_by_name(
    db: AsyncSession, tenant_id: str, name: str
) -> ProductHit | None:
    hits = await search_products(db, tenant_id, name, limit=1)
    return hits[0] if hits else None


PRODUCT_BY_SKU_SQL = text(
    """
    SELECT id::text, sku, name, description, size, price, stock, attributes
    FROM products
    WHERE tenant_id = :tenant_id AND upper(sku) = upper(:sku) AND is_active = true
    LIMIT 1
    """
)


async def get_product_by_sku(
    db: AsyncSession, tenant_id: str, sku: str
) -> ProductHit | None:
    """Exact SKU lookup — used for deep-link / QR / ad entry points."""
    row = (
        await db.execute(PRODUCT_BY_SKU_SQL, {"tenant_id": tenant_id, "sku": sku})
    ).first()
    if not row:
        return None
    return ProductHit(
        id=row[0], sku=row[1], name=row[2], description=row[3] or "", size=row[4],
        price=float(row[5]), stock=int(row[6]), attributes=row[7] or {}, rank=1.0,
    )
