import hashlib
import json

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("redis")


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RedisService:
    def __init__(self) -> None:
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def ping(self) -> bool:
        try:
            return bool(await self.client.ping())
        except Exception as exc:  # noqa: BLE001
            log.warning({"event": "redis_unavailable", "error": str(exc)})
            return False

    # ---------- webhook idempotency ----------

    async def claim_message(self, wamid: str, ttl: int = 86400) -> bool:
        """True if this wamid has not been seen before.

        Meta retries webhooks for up to 7 days; without this you double-reply.
        """
        try:
            return bool(await self.client.set(f"seen:{wamid}", "1", ex=ttl, nx=True))
        except Exception as exc:  # noqa: BLE001
            log.warning({"event": "dedupe_failed_open", "error": str(exc)})
            return True  # fail open: better a rare duplicate than dropped messages

    # ---------- answer cache (facts only) ----------

    def cache_key(self, tenant_id: str, normalized_q: str) -> str:
        return f"ans:{tenant_id}:{hash_text(normalized_q)}"

    def _meta(self) -> dict:
        return {
            "prompt_version": settings.CACHE_PROMPT_VERSION,
            "retrieval_version": settings.CACHE_RETRIEVAL_VERSION,
            "model": settings.GEMINI_MODEL,
        }

    async def get_answer(self, key: str) -> str | None:
        try:
            raw = await self.client.get(key)
        except Exception:  # noqa: BLE001
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        # Version guard: a cached answer produced by older prompt/retrieval
        # logic must not be served after we change that logic.
        if payload.get("meta") != self._meta():
            return None
        return payload.get("answer")

    async def set_answer(self, key: str, answer: str) -> None:
        payload = json.dumps({"answer": answer, "meta": self._meta()})
        try:
            await self.client.set(key, payload, ex=settings.CACHE_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001
            log.warning({"event": "cache_write_failed", "error": str(exc)})

    async def clear_tenant_cache(self, tenant_id: str) -> None:
        """Call after a catalog/FAQ upload so stale answers stop being served."""
        pattern = f"ans:{tenant_id}:*"
        cursor = 0
        while True:
            cursor, keys = await self.client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                await self.client.delete(*keys)
            if cursor == 0:
                break

    # ---------- embedding cache ----------

    async def get_embedding(self, text: str) -> list[float] | None:
        key = f"embed:{settings.GEMINI_EMBEDDING_MODEL}:{hash_text(text)}"
        try:
            raw = await self.client.get(key)
            return json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001
            return None

    async def set_embedding(self, text: str, vector: list[float]) -> None:
        key = f"embed:{settings.GEMINI_EMBEDDING_MODEL}:{hash_text(text)}"
        try:
            await self.client.set(
                key, json.dumps(vector), ex=settings.EMBED_CACHE_TTL_SECONDS
            )
        except Exception:  # noqa: BLE001
            pass

    # ---------- rate limiting ----------

    async def is_rate_limited(self, tenant_id: str, wa_id: str) -> bool:
        key = f"rate:{tenant_id}:{wa_id}"
        try:
            count = await self.client.incr(key)
            if count == 1:
                await self.client.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)
            return count > settings.RATE_LIMIT_MESSAGES
        except Exception:  # noqa: BLE001
            return False

    # ---------- short conversation history ----------

    async def add_history(self, conversation_id: str, user: str, bot: str) -> None:
        key = f"hist:{conversation_id}"
        try:
            await self.client.rpush(key, json.dumps({"user": user, "bot": bot}))
            await self.client.ltrim(key, -10, -1)
            await self.client.expire(key, 86400)
        except Exception:  # noqa: BLE001
            pass

    async def get_history(self, conversation_id: str, limit: int = 5) -> list[dict]:
        key = f"hist:{conversation_id}"
        try:
            raw = await self.client.lrange(key, -limit, -1)
            return [json.loads(item) for item in raw]
        except Exception:  # noqa: BLE001
            return []


redis_service = RedisService()
