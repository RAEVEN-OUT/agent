"""Shared text signals used by both the deterministic classifier and catalog Q&A.

Kept in its own module so `fast_intent` does not have to import the retrieval
stack (and drag in the LLM/Qdrant clients) just to ask "is this advisory?".
"""

# Never answer these from a cache, template, or keyword rule. They need
# judgement, and judgement is what earns the sale.
ADVISORY_MARKERS = (
    "which", "better", "best", "suggest", "recommend", "should i", "suitable",
    "good for", "vs", "or ", "compare", "difference between", "help me choose",
    "what do you think", "advice", "advise",
)

# Pure fact lookups: safe to cache and to answer from a template.
FACTUAL_MARKERS = (
    "delivery charge", "shipping charge", "do you ship", "return policy",
    "exchange policy", "how many days", "timing", "open", "cod available",
    "cash on delivery available", "gst", "invoice", "working hours",
    "vegan", "cruelty free", "sulphate", "paraben",
)


def is_advisory(normalized: str) -> bool:
    return any(marker in normalized for marker in ADVISORY_MARKERS)


def is_factual(normalized: str) -> bool:
    return any(marker in normalized for marker in FACTUAL_MARKERS)
