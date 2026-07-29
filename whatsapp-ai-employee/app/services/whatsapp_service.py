import hashlib
import hmac

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.retry import external_retry

log = get_logger("whatsapp")


class WhatsAppService:
    def __init__(self) -> None:
        self.base = "https://graph.facebook.com"

    def _url(self, phone_number_id: str) -> str:
        return f"{self.base}/{settings.WHATSAPP_API_VERSION}/{phone_number_id}/messages"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    # ---------- inbound security ----------

    def verify_signature(self, raw_body: bytes, header_value: str | None) -> bool:
        """Validate X-Hub-Signature-256 so only Meta can post to the webhook."""
        if not settings.VERIFY_WEBHOOK_SIGNATURE:
            return True
        if not header_value or not settings.WHATSAPP_APP_SECRET:
            return False
        expected = hmac.new(
            settings.WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        received = header_value.removeprefix("sha256=")
        return hmac.compare_digest(expected, received)

    # ---------- outbound ----------

    @external_retry
    async def send_text(self, phone_number_id: str, to: str, body: str) -> dict:
        """Free-form reply. Only valid inside the 24h customer service window."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body[:4096]},
        }
        return await self._post(phone_number_id, payload)

    @external_retry
    async def send_template(
        self,
        phone_number_id: str,
        to: str,
        template_name: str,
        language: str = "en_US",
        body_params: list[str] | None = None,
    ) -> dict:
        """Required for anything outside the 24h window (follow-ups, campaigns)."""
        components = []
        if body_params:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in body_params],
                }
            )
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components,
            },
        }
        return await self._post(phone_number_id, payload)

    @external_retry
    async def mark_read(self, phone_number_id: str, wamid: str) -> None:
        payload = {"messaging_product": "whatsapp", "status": "read", "message_id": wamid}
        await self._post(phone_number_id, payload)

    async def _post(self, phone_number_id: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                self._url(phone_number_id), headers=self._headers(), json=payload
            )
        if resp.status_code >= 400:
            log.error(
                {
                    "event": "whatsapp_send_failed",
                    "status": resp.status_code,
                    "response": resp.text[:500],
                    "type": payload.get("type"),
                }
            )
            resp.raise_for_status()
        return resp.json()

    async def get_media_url(self, media_id: str) -> str | None:
        url = f"{self.base}/{settings.WHATSAPP_API_VERSION}/{media_id}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=self._headers())
        if resp.status_code >= 400:
            return None
        return resp.json().get("url")


whatsapp_service = WhatsAppService()
