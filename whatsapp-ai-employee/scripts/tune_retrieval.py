"""Show what retrieval actually scores, so FTS_FAST_PATH_RANK can be tuned.

The fast-path threshold decides how many messages cost a model call. Set it too
high and nothing ever fast-paths (every question hits the LLM); too low and the
bot confidently answers with the wrong FAQ. Neither is guessable — measure it.

Run:  docker compose exec api python -m scripts.tune_retrieval
      docker compose exec api python -m scripts.tune_retrieval --semantic

Uses no LLM calls unless --semantic is passed (which needs embeddings).
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Tenant
from app.db.session import SessionLocal
from app.modules import retrieval
from app.modules.catalog_qa import is_advisory
from app.pipeline.normalize import normalize

# (question, should_fast_path)
# "should" = is this a factual question we want answered with zero model calls?
PROBES: list[tuple[str, bool]] = [
    ("what are the delivery charges", True),
    ("delivery charge", True),
    ("how much is shipping", True),
    ("how long does delivery take", True),
    ("when will it arrive", True),
    ("do you have cod", True),
    ("is cash on delivery available", True),
    ("what is your return policy", True),
    ("can i return it", True),
    ("are the products vegan", True),
    ("is it cruelty free", True),
    ("sulphate free?", True),
    ("what are your working hours", True),
    ("do you deliver to coimbatore", True),
    # These must NOT fast-path — they need judgement.
    ("which shampoo is good for dandruff", False),
    ("what should i use for hair fall", False),
    ("suggest something for dry hair", False),
    ("argan oil or serum which is better", False),
    ("how much is the argan oil", False),  # product lookup, not an FAQ
    ("do you have the 200ml", False),
]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semantic", action="store_true", help="also test vector search")
    args = parser.parse_args()

    async with SessionLocal() as db:
        tenant = (
            await db.execute(select(Tenant).order_by(Tenant.created_at).limit(1))
        ).scalar_one_or_none()
        if not tenant:
            raise SystemExit("No tenant. Run: python -m scripts.seed_demo")

        tid = str(tenant.id)
        threshold = settings.FTS_FAST_PATH_RANK
        print(f"\nTenant: {tenant.name}")
        print(f"FTS_FAST_PATH_RANK = {threshold}\n")
        print(f"{'question':<40} {'faq_rank':>9} {'prod':>5} {'adv':>4} {'fast?':>6}  verdict")
        print("-" * 92)

        false_neg = false_pos = 0
        ranks_wanted: list[float] = []
        ranks_unwanted: list[float] = []

        for question, should in PROBES:
            norm = normalize(question)
            advisory = is_advisory(norm)
            faqs = await retrieval.search_faqs(db, tid, norm, limit=1)
            products = await retrieval.search_products(db, tid, norm, limit=3)
            rank = faqs[0].rank if faqs else 0.0

            would_fast_path = bool(faqs) and rank >= threshold and not advisory

            if should:
                ranks_wanted.append(rank)
            else:
                ranks_unwanted.append(rank)

            verdict = "ok"
            if should and not would_fast_path:
                verdict = "MISS -> costs an LLM call"
                false_neg += 1
            elif not should and would_fast_path:
                verdict = "WRONG -> canned answer to a judgement question"
                false_pos += 1

            print(
                f"{question[:39]:<40} {rank:>9.4f} {len(products):>5} "
                f"{'yes' if advisory else '-':>4} "
                f"{'YES' if would_fast_path else 'no':>6}  {verdict}"
            )

        print("-" * 92)
        print(f"missed fast paths (wasted money): {false_neg}")
        print(f"wrong fast paths (wrong answers): {false_pos}")

        if ranks_wanted:
            hits = [r for r in ranks_wanted if r > 0]
            if hits:
                print(
                    f"\nfactual questions that matched an FAQ: min={min(hits):.4f} "
                    f"max={max(hits):.4f}"
                )
                print(
                    "  -> set FTS_FAST_PATH_RANK just below that min, "
                    f"e.g. {max(0.01, min(hits) * 0.9):.3f}"
                )
            zero = len(ranks_wanted) - len(hits)
            if zero:
                print(
                    f"  -> {zero} factual question(s) matched NO FAQ lexically. "
                    "Those need semantic search (run with --semantic) or a new FAQ entry."
                )
        if ranks_unwanted:
            worst = max(ranks_unwanted)
            print(f"\nhighest rank among judgement questions: {worst:.4f}")
            print("  -> keep the threshold above this to avoid canned sales answers")

        if not args.semantic:
            print("\n(add --semantic to test vector fallback — uses embeddings)")
            return

        print("\n" + "=" * 92)
        print("semantic fallback (only matters when FTS finds nothing)\n")
        for question, should in PROBES:
            norm = normalize(question)
            faqs = await retrieval.search_faqs(db, tid, norm, limit=1)
            if faqs and faqs[0].rank >= threshold:
                continue  # already handled for free
            chunks = await retrieval.semantic_search_chunks(tid, norm, limit=1)
            if chunks:
                top = chunks[0]
                label = top.metadata.get("question") or top.metadata.get("name") or "?"
                print(f"  {question[:38]:<40} {top.score:.4f}  <- {str(label)[:34]}")
            else:
                print(f"  {question[:38]:<40} {'--':>6}  nothing above SEMANTIC_MIN_SCORE")
        print(f"\nSEMANTIC_MIN_SCORE = {settings.SEMANTIC_MIN_SCORE}")


if __name__ == "__main__":
    asyncio.run(main())
