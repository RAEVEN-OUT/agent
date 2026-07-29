import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.core.logging import get_logger

log = get_logger("events")

Handler = Callable[[str, dict[str, Any]], Awaitable[None]]


class EventBus:
    """Internal event bus + optional outbound webhooks.

    Why this exists: per-client integrations ("also log to my Google Sheet",
    "ping me on Telegram") should never touch core code. They subscribe here
    instead. Same hook lets n8n or any external tool consume events later
    without a rewrite.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}
        self._outbound: list[str] = []

    def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def add_outbound_webhook(self, url: str) -> None:
        self._outbound.append(url)

    async def emit(self, event: str, payload: dict[str, Any]) -> None:
        log.info({"event": "domain_event", "name": event, "payload": payload})

        handlers = self._handlers.get(event, []) + self._handlers.get("*", [])
        for handler in handlers:
            try:
                await handler(event, payload)
            except Exception as exc:  # noqa: BLE001  a bad connector must not break the flow
                log.error({"event": "handler_failed", "name": event, "error": str(exc)})

        if self._outbound:
            asyncio.create_task(self._post_outbound(event, payload))

    async def _post_outbound(self, event: str, payload: dict[str, Any]) -> None:
        body = {"event": event, "data": payload}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in self._outbound:
                try:
                    await client.post(url, json=body)
                except Exception as exc:  # noqa: BLE001
                    log.warning({"event": "outbound_webhook_failed", "url": url, "error": str(exc)})


event_bus = EventBus()

# Canonical event names — keep connectors coupled to these, not to internals.
ORDER_CREATED = "order.created"
ORDER_STATUS_CHANGED = "order.status_changed"
PAYMENT_RECEIVED = "payment.received"
ESCALATION_RAISED = "escalation.raised"
CUSTOMER_CREATED = "customer.created"
MESSAGE_RECEIVED = "message.received"
