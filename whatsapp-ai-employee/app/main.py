from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, webhook
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.session import init_models
from app.services.qdrant_service import qdrant_service

setup_logging()
log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info({"event": "startup", "env": settings.ENV})

    if settings.AUTO_CREATE_TABLES:
        try:
            await init_models()
            log.info({"event": "tables_ready"})
        except Exception as exc:  # noqa: BLE001
            log.error({"event": "table_init_failed", "error": str(exc)})

    try:
        await qdrant_service.ensure_collection()
    except Exception as exc:  # noqa: BLE001
        log.warning({"event": "qdrant_init_skipped", "error": str(exc)})

    yield
    log.info({"event": "shutdown"})


app = FastAPI(title=settings.PROJECT_NAME, version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(webhook.router)


@app.get("/")
async def root() -> dict:
    return {"service": settings.PROJECT_NAME, "status": "running"}
