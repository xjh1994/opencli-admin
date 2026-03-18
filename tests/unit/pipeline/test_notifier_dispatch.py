"""Unit tests for notifier_dispatch."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.pipeline.notifier_dispatch import dispatch_notifications


@pytest.mark.asyncio
async def test_dispatch_empty_records(db_session):
    await dispatch_notifications(db_session, "src-1", [], "on_new_record")
    # Should return without doing anything


@pytest.mark.asyncio
async def test_dispatch_no_matching_rules(db_session):
    record = MagicMock()
    record.id = "rec-1"
    record.normalized_data = {"title": "Test"}
    record.ai_enrichment = None

    # No rules in DB - should succeed silently
    await dispatch_notifications(db_session, "src-1", [record], "on_new_record")


@pytest.mark.asyncio
async def test_dispatch_with_matching_rule(db_session):
    from backend.models.notification import NotificationRule
    from backend.models.source import DataSource

    source = DataSource(
        name="Notif Source",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed"},
    )
    db_session.add(source)
    await db_session.flush()

    rule = NotificationRule(
        name="Test Rule",
        trigger_event="on_new_record",
        notifier_type="webhook",
        notifier_config={"url": "https://hooks.ex.com"},
        enabled=True,
    )
    db_session.add(rule)
    await db_session.flush()

    record = MagicMock()
    record.id = "rec-1"
    record.normalized_data = {"title": "Test"}
    record.ai_enrichment = None

    mock_notifier = AsyncMock()
    mock_notifier.send = AsyncMock(return_value=True)

    with patch("backend.pipeline.notifier_dispatch.get_notifier", return_value=mock_notifier):
        await dispatch_notifications(db_session, source.id, [record], "on_new_record")

    mock_notifier.send.assert_awaited_once()
