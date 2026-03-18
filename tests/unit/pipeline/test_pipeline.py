"""Unit tests for the pipeline orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.channels.base import ChannelResult
from backend.pipeline.pipeline import PipelineResult, run_pipeline


@pytest.mark.asyncio
async def test_run_pipeline_success(db_session):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="Pipeline Test Source",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    mock_items = [
        {"title": "Item 1", "url": "https://ex.com/1"},
        {"title": "Item 2", "url": "https://ex.com/2"},
    ]
    channel_result = ChannelResult.ok(mock_items)

    with patch("backend.pipeline.collector.collect", return_value=channel_result):
        result = await run_pipeline(
            db_session,
            source,
            task.id,
            parameters={},
            enable_ai=False,
            enable_notifications=False,
        )

    assert result.success is True
    assert result.collected == 2
    assert result.stored == 2
    assert result.skipped == 0


@pytest.mark.asyncio
async def test_run_pipeline_channel_failure(db_session):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="Fail Source",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    channel_result = ChannelResult.fail("Connection refused")

    with patch("backend.pipeline.collector.collect", return_value=channel_result):
        result = await run_pipeline(db_session, source, task.id)

    assert result.success is False
    assert result.error == "Connection refused"


@pytest.mark.asyncio
async def test_run_pipeline_empty_channel(db_session):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="Empty Source",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    with patch("backend.pipeline.collector.collect", return_value=ChannelResult.ok([])):
        result = await run_pipeline(
            db_session, source, task.id, enable_ai=False, enable_notifications=False
        )

    assert result.success is True
    assert result.collected == 0
    assert result.stored == 0
