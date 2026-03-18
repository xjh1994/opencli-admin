"""Tests for pipeline error handling branches."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.channels.base import ChannelResult
from backend.pipeline.pipeline import run_pipeline


@pytest.mark.asyncio
async def test_pipeline_storage_error(db_session):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="Storage Error Source",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    items = [{"title": "Item"}]
    channel_result = ChannelResult.ok(items)

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch("backend.pipeline.storer.store_records", side_effect=Exception("DB error")),
    ):
        result = await run_pipeline(db_session, source, task.id)

    assert result.success is False
    assert "DB error" in result.error


@pytest.mark.asyncio
async def test_pipeline_collect_exception(db_session):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="Collect Exc Source",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    with patch("backend.pipeline.collector.collect", side_effect=RuntimeError("network down")):
        result = await run_pipeline(db_session, source, task.id)

    assert result.success is False
    assert "network down" in result.error


@pytest.mark.asyncio
async def test_pipeline_with_ai_failure_still_returns_success(db_session):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="AI Fail Source",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed.xml"},
        ai_config={"processor_type": "claude"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    items = [{"title": "Test Item"}]
    channel_result = ChannelResult.ok(items)

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch(
            "backend.pipeline.ai_processor.process_with_ai",
            side_effect=Exception("AI service down"),
        ),
    ):
        result = await run_pipeline(
            db_session, source, task.id, enable_ai=True, enable_notifications=False
        )

    # AI failure is a warning, pipeline still succeeds
    assert result.success is True
