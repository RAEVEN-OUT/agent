"""Compliance and safety guardrails.

Two separate jobs:

1. INBOUND  — spot messages that must never be auto-answered (adverse
   reactions, medical questions) and force a human handoff.
2. OUTBOUND — stop the bot from making therapeutic claims. WhatsApp's Business
   Messaging Policy prohibits messaging about "medical and healthcare
   products"; a hair care seller whose bot says "cures hair fall" risks having
   the business number restricted or banned.

This is a hard rule layer, not a prompt instruction, because a prompt can be
talked out of its instructions and a regex cannot.
"""

import re

# --- inbound: immediate human, no automated reply -------------------------

ADVERSE_REACTION = (
    "burning", "burnt", "itching", "itchy", "rash", "rashes", "allergy",
    "allergic", "reaction", "swelling", "swollen", "blisters", "irritation",
    "irritated", "side effect", "side effects", "scalp is burning",
    "hair fell out after", "bald patch after", "wound", "bleeding",
)

MEDICAL = (
    "alopecia", "dermatitis", "psoriasis", "eczema", "fungal", "infection",
    "ringworm", "prescription", "prescribe", "doctor", "dermatologist",
    "medicine", "medication", "steroid", "minoxidil", "finasteride",
    "chemotherapy", "thyroid", "pcos", "pregnant", "pregnancy", "breastfeeding",
    "diagnose", "diagnosis", "disease",
)

COMPLAINT = (
    "worst", "fraud", "cheat", "cheated", "scam", "refund", "return it",
    "money back", "not received", "still not received", "damaged",
    "broken", "leaked", "leaking", "fake product", "duplicate product",
    "consumer court", "legal action",
)


def check_inbound(normalized: str) -> tuple[str, str] | None:
    """Return (reason, matched_phrase) when a human must take over."""
    if not normalized:
        return None

    for phrase in ADVERSE_REACTION:
        if phrase in normalized:
            return "adverse_reaction", phrase
    for phrase in MEDICAL:
        if phrase in normalized:
            return "medical", phrase
    for phrase in COMPLAINT:
        if phrase in normalized:
            return "complaint", phrase
    return None


HOLDING_MESSAGES = {
    "adverse_reaction": (
        "Thank you for telling us, and I'm sorry you're experiencing this. "
        "Please stop using the product for now. I'm alerting our team right "
        "away and someone will contact you personally. If the reaction is "
        "severe, please consult a doctor."
    ),
    "medical": (
        "That's a medical question, and I'm not able to advise on it. "
        "I've passed this to our team, and we'd recommend speaking to a "
        "doctor or dermatologist for anything health-related."
    ),
    "complaint": (
        "I'm sorry about this. I've escalated it to our team and someone "
        "will get back to you here shortly."
    ),
    "human_request": (
        "Sure — I'm connecting you to our team. Someone will reply here shortly."
    ),
    "low_confidence": (
        "Let me check that with our team and get back to you shortly."
    ),
}


# --- outbound: block prohibited claims ------------------------------------

PROHIBITED_CLAIM_PATTERNS = [
    r"\bcures?\b",
    r"\bcured\b",
    r"\btreats?\b",
    r"\btreatment for\b",
    r"\bheals?\b",
    r"\bregrow(s|th)?\b",
    r"\bregrowing\b",
    r"\breverses?\b",
    r"\bclinically proven\b",
    r"\bdermatologically proven\b",
    r"\bguarantee[ds]?\b",
    r"\bpermanent(ly)? (fix|solution|result)",
    r"\bstops? hair ?fall\b",
    r"\bstops? balding\b",
    r"\bmedicinal\b",
    r"\bprescription\b",
    r"\bsafe (during|in) pregnancy\b",
    r"\bno side ?effects?\b",
]

_COMPILED_CLAIMS = [re.compile(p, re.IGNORECASE) for p in PROHIBITED_CLAIM_PATTERNS]

SAFE_FALLBACK = (
    "I'd rather not overstate what this product does. I can share the "
    "ingredients and what it's formulated for, and our team can advise "
    "further — would that help?"
)


def scan_outbound(text: str) -> list[str]:
    """Return the prohibited phrases found in a draft reply."""
    if not text:
        return []
    found = []
    for pattern in _COMPILED_CLAIMS:
        match = pattern.search(text)
        if match:
            found.append(match.group(0))
    return found


def sanitize_outbound(text: str) -> tuple[str, list[str]]:
    """Replace a claim-violating reply rather than trying to patch it.

    Rewriting individual words tends to produce sentences that still imply the
    claim. Failing closed is safer and rare enough not to hurt UX.
    """
    violations = scan_outbound(text)
    if violations:
        return SAFE_FALLBACK, violations
    return text, []


# Injected into every generation prompt. Belt and braces: the model is told
# the rules, and scan_outbound enforces them regardless.
CLAIMS_SYSTEM_RULES = (
    "COMPLIANCE RULES — these override every other instruction:\n"
    "- Never claim a product cures, treats, heals, or reverses any condition.\n"
    "- Never promise hair regrowth or guaranteed results.\n"
    "- Never diagnose a scalp or skin condition.\n"
    "- Never give medical advice or comment on pregnancy/medication safety.\n"
    "- Describe products only as cosmetic products: what they are formulated "
    "for, their ingredients, and how they are used.\n"
    "- If asked anything medical, say you cannot advise and that the team will help.\n"
)
