"""Tests for error paths in notifier_dispatch."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.pipeline.notifier_dispatch import dispatch_notifications


@pytest.mark.asyncio
async def test_dispatch_unknown_notifier_type_skipped(db_session):
    from backend.models.notification import NotificationRule
    from backend.models.source import DataSource

    source = DataSource(
        name="Src",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed"},
    )
    db_session.add(source)
    await db_session.flush()

    rule = NotificationRule(
        name="Unknown Notifier",
        trigger_event="on_new_record",
        notifier_type="nonexistent_notifier",
        notifier_config={},
        enabled=True,
    )
    db_session.add(rule)
    await db_session.flush()

    record = AsyncMock()
    record.id = "rec-1"
    record.normalized_data = {"title": "Test"}
    record.ai_enrichment = None

    # Should silently skip unknown notifier (ValueError from get_notifier)
    await dispatch_notifications(db_session, source.id, [record], "on_new_record")


@pytest.mark.asyncio
async def test_dispatch_notifier_send_exception_logged(db_session):
    from backend.models.notification import NotificationRule
    from backend.models.source import DataSource

    source = DataSource(
        name="Exc Src",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed"},
    )
    db_session.add(source)
    await db_session.flush()

    rule = NotificationRule(
        name="Failing Rule",
        trigger_event="on_new_record",
        notifier_type="webhook",
        notifier_config={"url": "https://hooks.ex.com"},
        enabled=True,
    )
    db_session.add(rule)
    await db_session.flush()

    record = AsyncMock()
    record.id = "rec-2"
    record.normalized_data = {}
    record.ai_enrichment = None

    mock_notifier = AsyncMock()
    mock_notifier.send = AsyncMock(side_effect=Exception("connection refused"))

    with patch("backend.pipeline.notifier_dispatch.get_notifier", return_value=mock_notifier):
        # Should catch exception and log as failed, not raise
        await dispatch_notifications(db_session, source.id, [record], "on_new_record")
