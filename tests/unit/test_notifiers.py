"""Unit tests for notifier base classes and webhook notifier."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.notifiers.base import NotificationPayload
from backend.notifiers.registry import get_notifier, list_notifier_types
from backend.notifiers.webhook_notifier import WebhookNotifier


def test_notifier_registry_has_webhook():
    types = list_notifier_types()
    assert "webhook" in types


def test_get_notifier_valid():
    notifier = get_notifier("webhook")
    assert notifier.notifier_type == "webhook"


def test_get_notifier_invalid():
    from backend.notifiers.registry import get_notifier
    with pytest.raises(ValueError):
        get_notifier("nonexistent_notifier")


def test_notification_payload_defaults():
    payload = NotificationPayload(event="on_new_record", source_id="src-123")
    assert payload.event == "on_new_record"
    assert payload.source_id == "src-123"
    assert payload.record_id is None
    assert payload.ai_enrichment is None
    assert payload.data == {}


@pytest.mark.asyncio
async def test_webhook_notifier_send_success():
    notifier = WebhookNotifier()
    payload = NotificationPayload(
        event="on_new_record",
        source_id="src-1",
        record_id="rec-1",
        data={"title": "Test"},
    )

    mock_response = MagicMock()
    mock_response.is_success = True

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await notifier.send(
            {"url": "https://hooks.example.com/notify"},
            payload,
        )

    assert result is True


@pytest.mark.asyncio
async def test_webhook_notifier_send_with_signature():
    notifier = WebhookNotifier()
    payload = NotificationPayload(event="test", source_id="src")

    captured_headers = {}

    async def mock_post(url, content, headers):
        captured_headers.update(headers)
        mock_resp = MagicMock()
        mock_resp.is_success = True
        return mock_resp

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        mock_client_class.return_value = mock_client

        await notifier.send(
            {"url": "https://hooks.ex.com/test", "secret": "my-secret"},
            payload,
        )

    assert "X-Signature-256" in captured_headers
    assert captured_headers["X-Signature-256"].startswith("sha256=")
