"""Webhook notifier: POST JSON payload to a URL."""

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from backend.notifiers.base import AbstractNotifier, NotificationPayload
from backend.notifiers.registry import register_notifier


@register_notifier
class WebhookNotifier(AbstractNotifier):
    notifier_type = "webhook"

    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> bool:
        url: str = config.get("url", "")
        secret: str = config.get("secret", "")
        timeout: int = config.get("timeout", 15)
        extra_headers: dict = config.get("headers", {})

        body = {
            "event": payload.event,
            "source_id": payload.source_id,
            "record_id": payload.record_id,
            "data": payload.data,
            "ai_enrichment": payload.ai_enrichment,
            "timestamp": int(time.time()),
        }
        body_bytes = json.dumps(body).encode()

        headers = {"Content-Type": "application/json", **extra_headers}
        if secret:
            sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
            headers["X-Signature-256"] = f"sha256={sig}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, content=body_bytes, headers=headers)
            return response.is_success
