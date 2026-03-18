"""Feishu (Lark) webhook notifier."""

import re
from typing import Any

import httpx

from backend.notifiers.base import AbstractNotifier, NotificationPayload
from backend.notifiers.registry import register_notifier

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _render(template: str, data: dict[str, Any]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: str(data.get(m.group(1), "")), template)


@register_notifier
class FeishuNotifier(AbstractNotifier):
    """Send notifications to Feishu via incoming webhook."""

    notifier_type = "feishu"

    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> bool:
        webhook_url: str = config.get("webhook_url", "")
        title_template: str = config.get("title", "New record: {{title}}")
        content_template: str = config.get("content", "Source: {{source_id}}\n{{title}}")
        timeout: int = config.get("timeout", 15)

        data = {"source_id": payload.source_id, **(payload.data or {})}
        title = _render(title_template, data)
        content = _render(content_template, data)

        body = {
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

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(webhook_url, json=body)
            result = resp.json()
            return result.get("StatusCode", result.get("code", -1)) == 0
