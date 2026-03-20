"""Unit tests for the pipeline orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.channels.base import ChannelResult
from backend.pipeline.pipeline import PipelineResult, run_pipeline


def _make_source(db_session, name="Pipeline Test Source", channel_type="rss"):
    from backend.models.source import DataSource
    return DataSource(
        name=name,
        channel_type=channel_type,
        channel_config={"feed_url": "https://ex.com/feed.xml"},
    )


async def _setup_source_task(db_session, channel_type="rss"):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="Pipeline Test Source",
        channel_type=channel_type,
        channel_config={"feed_url": "https://ex.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    return source, task


@pytest.mark.asyncio
async def test_run_pipeline_success(db_session):
    source, task = await _setup_source_task(db_session)

    mock_items = [
        {"title": "Item 1", "url": "https://ex.com/1"},
        {"title": "Item 2", "url": "https://ex.com/2"},
    ]
    channel_result = ChannelResult.ok(mock_items)
    mock_records = [MagicMock(), MagicMock()]

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch("backend.pipeline.storer.store_records", new=AsyncMock(return_value=(mock_records, 0))),
    ):
        result = await run_pipeline(
            task.id,
            source,
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
    source, task = await _setup_source_task(db_session)

    channel_result = ChannelResult.fail("Connection refused")

    with patch("backend.pipeline.collector.collect", return_value=channel_result):
        result = await run_pipeline(task.id, source)

    assert result.success is False
    assert result.error == "Connection refused"


@pytest.mark.asyncio
async def test_run_pipeline_empty_channel(db_session):
    source, task = await _setup_source_task(db_session)

    with patch("backend.pipeline.collector.collect", return_value=ChannelResult.ok([])):
        result = await run_pipeline(
            task.id, source, enable_ai=False, enable_notifications=False
        )

    assert result.success is True
    assert result.collected == 0
    assert result.stored == 0


@pytest.mark.asyncio
async def test_run_pipeline_collector_exception(db_session):
    """Exception in collect step returns failed PipelineResult."""
    source, task = await _setup_source_task(db_session)

    with patch("backend.pipeline.collector.collect", side_effect=RuntimeError("collect crash")):
        result = await run_pipeline(task.id, source, enable_ai=False, enable_notifications=False)

    assert result.success is False
    assert "collect crash" in result.error


@pytest.mark.asyncio
async def test_run_pipeline_with_ai(db_session):
    """Pipeline with ai_config calls process_with_ai."""
    source, task = await _setup_source_task(db_session)

    mock_items = [{"title": "AI Item", "url": "https://ex.com/ai"}]
    channel_result = ChannelResult.ok(mock_items)

    mock_record = MagicMock()
    mock_record.id = "rec-ai-1"
    mock_record.ai_enrichment = {"summary": "AI summary"}

    agent_config = {
        "processor_type": "claude",
        "model": "claude-3-haiku-20240307",
        "prompt_template": "Summarize: {{content}}",
    }

    # Mock the inner AsyncSessionLocal calls used for AI status update and enrichment save
    mock_inner_session = AsyncMock()
    mock_inner_session.get = AsyncMock(return_value=MagicMock())
    mock_inner_session.commit = AsyncMock()
    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=mock_inner_session)
    inner_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch("backend.pipeline.storer.store_records", new=AsyncMock(return_value=([mock_record], 0))),
        patch("backend.pipeline.ai_processor.process_with_ai", new=AsyncMock()),
        patch("backend.database.AsyncSessionLocal", return_value=inner_cm),
    ):
        result = await run_pipeline(
            task.id,
            source,
            agent_config=agent_config,
            enable_ai=True,
            enable_notifications=False,
        )

    assert result.success is True
    assert result.ai_processed == 1


@pytest.mark.asyncio
async def test_run_pipeline_with_notifications(db_session):
    """Pipeline with new records dispatches notifications."""
    source, task = await _setup_source_task(db_session)

    mock_items = [{"title": "Notify Item", "url": "https://ex.com/n"}]
    channel_result = ChannelResult.ok(mock_items)
    mock_record = MagicMock()

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch("backend.pipeline.storer.store_records", new=AsyncMock(return_value=([mock_record], 0))),
        patch("backend.pipeline.notifier_dispatch.dispatch_notifications", new=AsyncMock()),
    ):
        result = await run_pipeline(
            task.id,
            source,
            enable_ai=False,
            enable_notifications=True,
        )

    assert result.success is True


@pytest.mark.asyncio
async def test_run_pipeline_store_exception(db_session):
    """Exception in store step returns failed PipelineResult with collected count."""
    source, task = await _setup_source_task(db_session)

    mock_items = [{"title": "Item 1", "url": "https://ex.com/1"}]
    channel_result = ChannelResult.ok(mock_items)

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch("backend.pipeline.storer.store_records", new=AsyncMock(side_effect=RuntimeError("db error"))),
    ):
        result = await run_pipeline(
            task.id, source, enable_ai=False, enable_notifications=False
        )

    assert result.success is False
    assert result.collected == 1
    assert "db error" in result.error


@pytest.mark.asyncio
async def test_run_pipeline_ai_exception_continues(db_session):
    """AI processing exception is caught and pipeline still returns success."""
    source, task = await _setup_source_task(db_session)

    mock_items = [{"title": "Item", "url": "https://ex.com/x"}]
    channel_result = ChannelResult.ok(mock_items)
    mock_record = MagicMock()
    mock_record.ai_enrichment = None

    agent_config = {"processor_type": "claude", "model": "claude-haiku"}

    # Mock the inner AsyncSessionLocal for AI status update
    mock_inner_session = AsyncMock()
    mock_inner_session.get = AsyncMock(return_value=MagicMock())
    mock_inner_session.commit = AsyncMock()
    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=mock_inner_session)
    inner_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch("backend.pipeline.storer.store_records", new=AsyncMock(return_value=([mock_record], 0))),
        patch("backend.pipeline.ai_processor.process_with_ai", new=AsyncMock(side_effect=RuntimeError("ai crash"))),
        patch("backend.database.AsyncSessionLocal", return_value=inner_cm),
    ):
        result = await run_pipeline(
            task.id,
            source,
            agent_config=agent_config,
            enable_ai=True,
            enable_notifications=False,
        )

    # AI failure is warned but pipeline still succeeds
    assert result.success is True
    assert result.ai_processed == 0


@pytest.mark.asyncio
async def test_run_pipeline_no_ai_config_skips_ai(db_session):
    """enable_ai=True but no ai_config logs debug and skips AI step."""
    source, task = await _setup_source_task(db_session)

    mock_items = [{"title": "Item", "url": "https://ex.com/x"}]
    channel_result = ChannelResult.ok(mock_items)
    mock_record = MagicMock()

    mock_process_with_ai = AsyncMock()

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch("backend.pipeline.storer.store_records", new=AsyncMock(return_value=([mock_record], 0))),
        patch("backend.pipeline.ai_processor.process_with_ai", mock_process_with_ai),
    ):
        result = await run_pipeline(
            task.id,
            source,
            agent_config=None,  # No AI config
            enable_ai=True,     # AI enabled but no config
            enable_notifications=False,
        )

    # AI should not be called
    mock_process_with_ai.assert_not_called()
    assert result.success is True
    assert result.ai_processed == 0


@pytest.mark.asyncio
async def test_run_pipeline_notification_exception_continues(db_session):
    """Exception in notification step is caught and pipeline still returns success."""
    source, task = await _setup_source_task(db_session)

    mock_items = [{"title": "Notify Item", "url": "https://ex.com/n"}]
    channel_result = ChannelResult.ok(mock_items)
    mock_record = MagicMock()

    mock_dispatch = AsyncMock(side_effect=RuntimeError("notifier crash"))
    mock_inner_session = AsyncMock()
    mock_inner_session.commit = AsyncMock()
    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=mock_inner_session)
    inner_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.pipeline.collector.collect", return_value=channel_result),
        patch("backend.pipeline.storer.store_records", new=AsyncMock(return_value=([mock_record], 0))),
        patch("backend.pipeline.notifier_dispatch.dispatch_notifications", mock_dispatch),
        patch("backend.database.AsyncSessionLocal", return_value=inner_cm),
    ):
        result = await run_pipeline(
            task.id,
            source,
            enable_ai=False,
            enable_notifications=True,
        )

    # Notification failure is warned but pipeline still succeeds
    assert result.success is True


@pytest.mark.asyncio
async def test_run_pipeline_opencli_auto_binding(db_session):
    """OpenCLI source auto-resolves chrome_endpoint from browser binding."""
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="OpenCLI Source",
        channel_type="opencli",
        channel_config={"site": "example.com", "command": "list"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    mock_binding = MagicMock()
    mock_binding.browser_endpoint = "http://chrome:9222"

    mock_channel_result = ChannelResult.ok([{"id": 1}])

    mock_browser_session = AsyncMock()
    mock_browser_session.commit = AsyncMock()
    browser_cm = AsyncMock()
    browser_cm.__aenter__ = AsyncMock(return_value=mock_browser_session)
    browser_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.services.browser_service.get_binding_by_site", new=AsyncMock(return_value=mock_binding)),
        patch("backend.database.AsyncSessionLocal", return_value=browser_cm),
        patch("backend.pipeline.collector.collect", return_value=mock_channel_result),
        patch("backend.pipeline.storer.store_records", new=AsyncMock(return_value=([], 0))),
    ):
        result = await run_pipeline(
            task.id,
            source,
            parameters={},
            enable_ai=False,
            enable_notifications=False,
        )

    assert result.success is True
