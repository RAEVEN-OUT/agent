import re

EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f1e6-\U0001f1ff"
    "\U00002190-\U000021ff"
    "\U00002b00-\U00002bff"
    "\U0001f900-\U0001f9ff"
    "️"
    "‍"
    "]+",
    flags=re.UNICODE,
)

# Real customers type like this. Expanding shorthand before search/embedding
# measurably improves retrieval hit rate.
SHORTHAND = {
    r"\bu\b": "you",
    r"\bur\b": "your",
    r"\bpls\b": "please",
    r"\bplz\b": "please",
    r"\bthx\b": "thanks",
    r"\bdnt\b": "do not",
    r"\bdont\b": "do not",
    r"\bim\b": "i am",
    r"\bhw\b": "how",
    r"\bwht\b": "what",
    r"\bwt\b": "what",
    r"\bwhr\b": "where",
    r"\bwhn\b": "when",
    r"\babt\b": "about",
    r"\bqty\b": "quantity",
    r"\bavl\b": "available",
    r"\bavlbl\b": "available",
    r"\bcod\b": "cash on delivery",
    r"\bdel\b": "delivery",
    r"\bshampo\b": "shampoo",
    r"\bcondtioner\b": "conditioner",
    r"\bhairfal\b": "hair fall",
}


def normalize(text: str) -> str:
    """Lowercase, strip emoji, expand shorthand, collapse whitespace."""
    if not text:
        return ""
    q = text.lower().strip()
    q = EMOJI_PATTERN.sub(" ", q)
    for pattern, replacement in SHORTHAND.items():
        q = re.sub(pattern, replacement, q)
    q = re.sub(r"([.!?])\1+", r"\1", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def is_meaningless(normalized: str) -> bool:
    """True when there is nothing left to act on.

    Short-circuits before we burn a cache lookup, an FTS query and an
    embedding call on an empty or gibberish string.
    """
    if not normalized or not re.search(r"\w", normalized, flags=re.UNICODE):
        return True
    words = normalized.split()
    if not words:
        return True
    return all(re.fullmatch(r"(.)\1{3,}", w) for w in words)


FOLLOWUP_PRONOUNS = {"it", "its", "this", "that", "they", "them", "those", "these", "one"}
FOLLOWUP_PREFIXES = ("and ", "what about", "how about", "also ", "then ", "ok ", "okay ")


def looks_like_followup(normalized: str) -> bool:
    if not normalized:
        return False
    words = set(normalized.split())
    if len(words) <= 6 and (words & FOLLOWUP_PRONOUNS):
        return True
    return normalized.startswith(FOLLOWUP_PREFIXES)


TOPIC_CHANGE_MARKERS = (
    "?", "actually", "wait", "instead", "cancel", "forget", "nevermind",
    "never mind", "change", "how much", "price", "what about", "do you have",
    "which", "another", "different", "hold on", "stop",
)

QUESTION_WORDS = ("what", "which", "how", "why", "when", "where", "can you", "do you")


def looks_like_topic_change(normalized: str) -> bool:
    """Is this message a new question rather than an answer to ours?

    Used mid-flow (during order capture) to decide whether we can skip the LLM
    router entirely. A bare "641002" or "Aparna" is an answer; "actually how
    much is the 200ml?" is not.

    Deliberately biased toward returning True: a false positive costs one model
    call, a false negative shoves a real question into an address field.
    """
    if not normalized:
        return False
    if any(marker in normalized for marker in TOPIC_CHANGE_MARKERS):
        return True
    if normalized.startswith(QUESTION_WORDS):
        return True
    # Long free text mid-flow is usually an address, so length alone is not a
    # signal — only the markers above are.
    return False


def local_rewrite(normalized: str, last_topic: str) -> str:
    """Zero-cost follow-up resolution.

    "what about the 200ml" + last topic "argan hair oil" -> a searchable query,
    without paying for an LLM rewrite call.
    """
    if not last_topic:
        return normalized
    return f"{last_topic} {normalized}".strip()
