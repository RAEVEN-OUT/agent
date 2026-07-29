"""Check that the credentials in .env actually work.

Run this first, on the machine that has network access:
    docker compose exec api python -m scripts.verify_credentials

Read-only. It never sends a WhatsApp message to anyone.
"""

import asyncio

import httpx

from app.core.config import settings


def mask(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


async def check_whatsapp() -> bool:
    print("\n[1] WhatsApp Cloud API")
    print(f"    token            {mask(settings.WHATSAPP_ACCESS_TOKEN)}")
    print(f"    phone_number_id  {settings.WHATSAPP_PHONE_NUMBER_ID or '(empty)'}")

    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        print("    FAIL: missing token or phone number id")
        return False

    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}"
    )
    params = {
        "fields": "display_phone_number,verified_name,quality_rating,"
        "whatsapp_business_manager_messaging_limit"
    }
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params, headers=headers)
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: network error - {exc}")
        return False

    data = resp.json()
    if "error" in data:
        err = data["error"]
        print(f"    FAIL: [{err.get('code')}] {err.get('message')}")
        if err.get("code") == 190:
            print("    -> token expired or invalid. If you used the temporary token")
            print("       from the API Setup panel, create a System User token instead")
            print("       (checklist section 1f).")
        return False

    for key, value in data.items():
        print(f"    OK   {key}: {value}")
    return True


async def check_templates() -> bool:
    print("\n[2] WhatsApp message templates")
    if not settings.WHATSAPP_BUSINESS_ACCOUNT_ID:
        print("    SKIP: WHATSAPP_BUSINESS_ACCOUNT_ID not set")
        return True

    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates"
    )
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                url, params={"fields": "name,status,category", "limit": "10"}, headers=headers
            )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: {exc}")
        return False

    if "error" in data:
        print(f"    FAIL: {data['error'].get('message')}")
        return False

    templates = data.get("data", [])
    print(f"    OK   {len(templates)} template(s) visible")
    for t in templates[:8]:
        print(f"         - {t.get('name')} [{t.get('status')}] {t.get('category', '')}")
    return True


async def check_gemini() -> bool:
    print("\n[3] Gemini")
    print(f"    key    {mask(settings.GEMINI_API_KEY)}")
    print(f"    model  {settings.GEMINI_MODEL}")

    if not settings.GEMINI_API_KEY:
        print("    FAIL: GEMINI_API_KEY empty")
        return False

    try:
        from app.services.llm_service import llm_service

        result = await llm_service.generate(
            "Reply with exactly: OK", "ping", max_output_tokens=10
        )
        print(f"    OK   generation -> {result.text!r} "
              f"({result.input_tokens}+{result.output_tokens} tokens)")
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: generation - {exc}")
        return False

    try:
        vector = await llm_service.embed("hair oil for dry hair")
        print(f"    OK   embedding -> {len(vector)} dimensions")
        if len(vector) != settings.GEMINI_EMBEDDING_DIMENSIONS:
            print(
                f"    WARN: expected {settings.GEMINI_EMBEDDING_DIMENSIONS} dims. "
                "Update GEMINI_EMBEDDING_DIMENSIONS and recreate the Qdrant "
                "collection, or vector search will fail."
            )
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: embedding - {exc}")
        return False

    return True


async def check_infra() -> bool:
    print("\n[4] Infrastructure")
    ok = True

    try:
        from sqlalchemy import text

        from app.db.session import SessionLocal

        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        print("    OK   postgres")
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: postgres - {exc}")
        ok = False

    try:
        from app.services.redis_service import redis_service

        print("    OK   redis" if await redis_service.ping() else "    FAIL: redis")
        ok = ok and await redis_service.ping()
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: redis - {exc}")
        ok = False

    try:
        from app.services.qdrant_service import qdrant_service

        if await qdrant_service.ping():
            print("    OK   qdrant")
        else:
            print("    FAIL: qdrant")
            ok = False
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: qdrant - {exc}")
        ok = False

    return ok


async def main() -> None:
    print("=" * 60)
    print("Credential & infrastructure check")
    print("=" * 60)

    results = {
        "whatsapp": await check_whatsapp(),
        "templates": await check_templates(),
        "gemini": await check_gemini(),
        "infra": await check_infra(),
    }

    print("\n" + "=" * 60)
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print("=" * 60)
    if all(results.values()):
        print("\nAll good. Next:  python -m scripts.seed_demo")
    else:
        print("\nFix the failures above before seeding.")


if __name__ == "__main__":
    asyncio.run(main())
