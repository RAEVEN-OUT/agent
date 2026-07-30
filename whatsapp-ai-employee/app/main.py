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

    # Check the WhatsApp token at boot rather than discovering it is dead when a
    # real customer messages and gets silence. Best-effort: never blocks startup.
    await _check_whatsapp_token()

    yield
    log.info({"event": "shutdown"})


async def _check_whatsapp_token() -> None:
    if not (settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID):
        log.warning({"event": "whatsapp_not_configured"})
        return

    import httpx

    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                params={"fields": "display_phone_number,verified_name,quality_rating"},
                headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning({"event": "whatsapp_token_check_skipped", "error": str(exc)})
        return

    error = data.get("error")
    if error:
        log.error(
            {
                "event": "whatsapp_token_invalid",
                "code": error.get("code"),
                "message": error.get("message"),
                "hint": (
                    "Token rejected. If you just rotated it, the container is still "
                    "holding the old value — env_file is read at container creation. "
                    "Run: docker compose down && docker compose up -d --force-recreate. "
                    "If it was the temporary token from the API Setup panel, it "
                    "expires in ~24h; create a System User token instead."
                )
                if error.get("code") == 190
                else None,
            }
        )
        return

    log.info(
        {
            "event": "whatsapp_token_ok",
            "number": data.get("display_phone_number"),
            "name": data.get("verified_name"),
            "quality": data.get("quality_rating"),
        }
    )


app = FastAPI(title=settings.PROJECT_NAME, version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(webhook.router)


@app.get("/")
async def root() -> dict:
    return {"service": settings.PROJECT_NAME, "status": "running"}
