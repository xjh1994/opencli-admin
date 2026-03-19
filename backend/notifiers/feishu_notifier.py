"""Feishu (Lark) webhook notifier."""

import base64
import hashlib
import hmac
import re
import time
from typing import Any

import httpx

from backend.notifiers.base import AbstractNotifier, NotificationPayload
from backend.notifiers.registry import register_notifier

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _render(template: str, data: dict[str, Any]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: str(data.get(m.group(1), "")), template)


def _feishu_sign(secret: str, timestamp: int) -> str:
    """Generate Feishu webhook signature (加签)."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


@register_notifier
class FeishuNotifier(AbstractNotifier):
    """Send notifications to Feishu via incoming webhook (custom bot)."""

    notifier_type = "feishu"

    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> bool:
        webhook_url: str = config.get("webhook_url", "")
        secret: str = config.get("secret", "")
        title_template: str = config.get("title", "【新采集】{{title}}")
        content_template: str = config.get(
            "content", "**来源**：{{source_id}}\n**标题**：{{title}}\n**链接**：{{url}}"
        )
        timeout: int = config.get("timeout", 15)

        data = {"source_id": payload.source_id, **(payload.data or {})}
        title = _render(title_template, data)
        content = _render(content_template, data)

        body: dict[str, Any] = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": [[{"tag": "text", "text": content}]],
                    }
                }
            },
        }

        if secret:
            ts = int(time.time())
            body["timestamp"] = str(ts)
            body["sign"] = _feishu_sign(secret, ts)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(webhook_url, json=body)
            result = resp.json()
            return result.get("code", -1) == 0
