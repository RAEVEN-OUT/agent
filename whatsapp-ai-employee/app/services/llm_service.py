import json
import re
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.core.retry import llm_retry
from app.services.redis_service import redis_service

log = get_logger("llm")

try:  # keep import failures from taking the whole app down at boot
    from google import genai
    from google.genai import types
except Exception:  # noqa: BLE001  pragma: no cover
    genai = None
    types = None


@dataclass
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


def _extract_json(raw: str) -> dict:
    """Parse a JSON object out of a model response.

    We ask for JSON via response_mime_type, but never trust that alone —
    models occasionally wrap it in prose or code fences.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


class LLMService:
    """Gemini primary. Provider-agnostic on purpose.

    To add a fallback provider, implement the same three methods and wire it
    into the except branches — nothing else in the codebase talks to the SDK.
    """

    def __init__(self) -> None:
        self.client = None
        if genai and settings.GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as exc:  # noqa: BLE001
                log.error({"event": "gemini_init_failed", "error": str(exc)})

    @property
    def available(self) -> bool:
        return self.client is not None

    def _usage(self, response) -> tuple[int, int]:
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return 0, 0
        return (
            getattr(usage, "prompt_token_count", 0) or 0,
            getattr(usage, "candidates_token_count", 0) or 0,
        )

    @llm_retry
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_output_tokens: int | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> LLMResult:
        if not self.client:
            raise RuntimeError("No LLM provider configured (GEMINI_API_KEY missing)")

        config_kwargs: dict = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS,
        }
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        response = await self.client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        text = (response.text or "").strip()
        in_tok, out_tok = self._usage(response)
        return LLMResult(text=text, input_tokens=in_tok, output_tokens=out_tok)

    async def generate_json(
        self, system_prompt: str, user_prompt: str, *, max_output_tokens: int | None = None
    ) -> tuple[dict, LLMResult]:
        result = await self.generate(
            system_prompt,
            user_prompt,
            max_output_tokens=max_output_tokens,
            temperature=0.0,
            json_mode=True,
        )
        return _extract_json(result.text), result

    @llm_retry
    async def embed(self, text: str) -> list[float]:
        """Embed with a 7-day cache. Cheap, but free is cheaper."""
        cached = await redis_service.get_embedding(text)
        if cached:
            return cached

        if not self.client:
            raise RuntimeError("No LLM provider configured (GEMINI_API_KEY missing)")

        response = await self.client.aio.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.GEMINI_EMBEDDING_DIMENSIONS
            ),
        )
        vector = list(response.embeddings[0].values)
        await redis_service.set_embedding(text, vector)
        return vector


llm_service = LLMService()
