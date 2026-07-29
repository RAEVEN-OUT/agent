from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class RateLimited(Exception):
    """Provider returned 429. Separated so callers can degrade instead of fail."""


def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


# Gemini free tier is 5 requests/minute and its 429 asks for ~10s. Waits must
# be long enough to actually clear that, or every retry burns and fails.
llm_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(Exception),
)

external_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.3, min=0.3, max=2),
    retry=retry_if_exception_type(Exception),
)
