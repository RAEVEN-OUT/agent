from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.llm_service import llm_service
from app.services.qdrant_service import qdrant_service
from app.services.redis_service import redis_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    postgres_ok = False
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:  # noqa: BLE001
        postgres_ok = False

    checks = {
        "postgres": postgres_ok,
        "redis": await redis_service.ping(),
        "qdrant": await qdrant_service.ping(),
        "llm_configured": llm_service.available,
    }
    checks["status"] = "ok" if all(
        v for k, v in checks.items() if k != "llm_configured"
    ) else "degraded"
    return checks
