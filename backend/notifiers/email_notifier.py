"""Email notifier via SMTP (aiosmtplib)."""

import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from backend.notifiers.base import AbstractNotifier, NotificationPayload
from backend.notifiers.registry import register_notifier


@register_notifier
class EmailNotifier(AbstractNotifier):
    notifier_type = "email"

    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> bool:
        try:
            import aiosmtplib
        except ImportError:
            raise RuntimeError("aiosmtplib package not installed")

        host = config.get("smtp_host") or os.environ.get("SMTP_HOST", "")
        port = int(config.get("smtp_port") or os.environ.get("SMTP_PORT", 587))
        user = config.get("smtp_user") or os.environ.get("SMTP_USER", "")
        password = config.get("smtp_password") or os.environ.get("SMTP_PASSWORD", "")
        from_addr = config.get("from") or os.environ.get("SMTP_FROM", user)
        to_addrs: list[str] = config.get("to", [])
        subject_template = config.get("subject", "New record: {{title}}")
        body_template = config.get("body", "Source: {{source_id}}\nTitle: {{title}}")

        def _render(template: str) -> str:
            import re
            data = {"source_id": payload.source_id, **payload.data}
            return re.sub(r"\{\{(\w+)\}\}", lambda m: str(data.get(m.group(1), "")), template)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = _render(subject_template)
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg.attach(MIMEText(_render(body_template), "plain"))

        await aiosmtplib.send(
            msg,
            hostname=host,
            port=port,
            username=user,
            password=password,
            start_tls=True,
        )
        return True
