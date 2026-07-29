import json
import re
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.core.retry import is_rate_limit_error, llm_retry
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
    thinking_tokens: int = 0
    finish_reason: str | None = None
    failed: bool = False
    rate_limited: bool = False


def _extract_json(raw: str) -> dict:
    """Parse a JSON object out of a model response.

    We ask for JSON via response_mime_type, but never trust that alone —
    models occasionally wrap it in prose or code fences.
    """
    raw = (raw or "").strip()
    if not raw:
        return {}
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


def _safe_text(response) -> str:
    """Get text without exploding when a candidate has no parts.

    A thinking model that hits max_output_tokens returns candidates with no
    text parts at all; `response.text` can raise or warn in that case.
    """
    try:
        direct = getattr(response, "text", None)
        if direct:
            return direct.strip()
    except Exception:  # noqa: BLE001
        pass

    chunks: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            # Skip the model's internal reasoning parts.
            if text and not getattr(part, "thought", False):
                chunks.append(text)
    return "".join(chunks).strip()


def _finish_reason(response) -> str | None:
    for candidate in getattr(response, "candidates", None) or []:
        reason = getattr(candidate, "finish_reason", None)
        if reason is not None:
            return getattr(reason, "name", str(reason))
    return None


class LLMService:
    """Gemini primary. Provider-agnostic on purpose.

    To add a fallback provider, implement the same methods and wire it into the
    except branches — nothing else in the codebase talks to the SDK.
    """

    def __init__(self) -> None:
        self.client = None
        self._thinking_supported = True
        if genai and settings.GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as exc:  # noqa: BLE001
                log.error({"event": "gemini_init_failed", "error": str(exc)})

    @property
    def available(self) -> bool:
        return self.client is not None

    def _usage(self, response) -> tuple[int, int, int]:
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return 0, 0, 0
        return (
            getattr(usage, "prompt_token_count", 0) or 0,
            getattr(usage, "candidates_token_count", 0) or 0,
            getattr(usage, "thoughts_token_count", 0) or 0,
        )

    def _build_config(
        self,
        system_prompt: str,
        max_output_tokens: int,
        temperature: float,
        json_mode: bool,
        disable_thinking: bool,
    ):
        kwargs: dict = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        if json_mode:
            kwargs["response_mime_type"] = "application/json"

        if disable_thinking and self._thinking_supported and types is not None:
            thinking_cls = getattr(types, "ThinkingConfig", None)
            if thinking_cls is not None:
                try:
                    kwargs["thinking_config"] = thinking_cls(thinking_budget=0)
                except Exception:  # noqa: BLE001
                    pass
        return types.GenerateContentConfig(**kwargs)

    @llm_retry
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_output_tokens: int | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        disable_thinking: bool | None = None,
        model: str | None = None,
    ) -> LLMResult:
        if not self.client:
            raise RuntimeError("No LLM provider configured (GEMINI_API_KEY missing)")

        cap = max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS
        model_name = model or settings.GEMINI_MODEL
        no_think = (
            settings.GEMINI_DISABLE_THINKING if disable_thinking is None else disable_thinking
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=self._build_config(
                    system_prompt, cap, temperature, json_mode, no_think
                ),
            )
        except Exception as exc:  # noqa: BLE001
            # Some models reject thinking_budget=0. Remember that and retry once
            # without it rather than failing every call from here on.
            if no_think and "thinking" in str(exc).lower():
                log.warning({"event": "thinking_config_unsupported", "error": str(exc)[:200]})
                self._thinking_supported = False
                response = await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=self._build_config(
                        system_prompt, cap, temperature, json_mode, False
                    ),
                )
            else:
                raise

        text = _safe_text(response)
        in_tok, out_tok, think_tok = self._usage(response)
        finish = _finish_reason(response)

        # Empty text is the failure mode that used to look like a parser bug.
        # Make it loud instead of silent.
        if not text:
            log.error(
                {
                    "event": "empty_llm_response",
                    "model": model_name,
                    "finish_reason": finish,
                    "max_output_tokens": cap,
                    "prompt_tokens": in_tok,
                    "output_tokens": out_tok,
                    "thinking_tokens": think_tok,
                    "hint": (
                        "raise LLM/ROUTER_MAX_OUTPUT_TOKENS or set "
                        "GEMINI_DISABLE_THINKING=true — a thinking model spent the "
                        "output budget before writing any text"
                    )
                    if finish in ("MAX_TOKENS", "LENGTH")
                    else None,
                }
            )

        return LLMResult(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            thinking_tokens=think_tok,
            finish_reason=finish,
            failed=not text,
        )

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> tuple[dict, LLMResult]:
        result = await self.generate(
            system_prompt,
            user_prompt,
            max_output_tokens=max_output_tokens or settings.ROUTER_MAX_OUTPUT_TOKENS,
            temperature=0.0,
            json_mode=True,
            model=model or settings.GEMINI_ROUTER_MODEL,
        )
        data = _extract_json(result.text)
        if result.text and not data:
            log.error(
                {
                    "event": "json_parse_failed",
                    "raw_response": result.text[:500],
                    "finish_reason": result.finish_reason,
                }
            )
        return data, result

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


def classify_failure(exc: Exception) -> str:
    return "rate_limited" if is_rate_limit_error(exc) else "error"


llm_service = LLMService()
