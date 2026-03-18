"""DingTalk (钉钉) webhook notifier."""

import hashlib
import hmac
import re
import time
import urllib.parse
from typing import Any

import httpx

from backend.notifiers.base import AbstractNotifier, NotificationPayload
from backend.notifiers.registry import register_notifier

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _render(template: str, data: dict[str, Any]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: str(data.get(m.group(1), "")), template)


def _dingtalk_sign(secret: str, timestamp: int) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    sig = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    import base64
    return urllib.parse.quote_plus(base64.b64encode(sig))


@register_notifier
class DingTalkNotifier(AbstractNotifier):
    """Send notifications to DingTalk via custom robot webhook."""

    notifier_type = "dingtalk"

    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> bool:
        webhook_url: str = config.get("webhook_url", "")
        secret: str = config.get("secret", "")
        title_template: str = config.get("title", "New record: {{title}}")
        content_template: str = config.get("content", "Source: {{source_id}}\n{{title}}")
        timeout: int = config.get("timeout", 15)

        data = {"source_id": payload.source_id, **(payload.data or {})}
        title = _render(title_template, data)
        content = _render(content_template, data)

        url = webhook_url
        if secret:
            ts = int(time.time() * 1000)
            sign = _dingtalk_sign(secret, ts)
            url = f"{webhook_url}&timestamp={ts}&sign={sign}"

        body = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n{content}",
            },
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            result = resp.json()
            return result.get("errcode", -1) == 0
