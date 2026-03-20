"""Unit tests for backend/scheduler.py."""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.scheduler import _is_due, start_scheduler, stop_scheduler


# ── _is_due tests ─────────────────────────────────────────────────────────────

def test_is_due_every_minute_just_fired():
    """Cron '* * * * *' fires every minute; should be due within last 60s."""
    now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert _is_due("* * * * *", now) is True


def test_is_due_specific_time_matches():
    """Cron expression that exactly matches current minute should be due."""
    # 12:05 UTC on June 1
    now = datetime(2024, 6, 1, 12, 5, 30, tzinfo=timezone.utc)
    # fires at 12:05 every day
    assert _is_due("5 12 * * *", now) is True


def test_is_due_future_time_not_due():
    """Cron for next hour should not be due now."""
    now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    # fires at 13:00 — hasn't fired yet in the last 60s
    assert _is_due("0 13 * * *", now) is False


def test_is_due_invalid_cron_expression():
    """Invalid cron expression should return False (no exception raised)."""
    now = datetime.now(timezone.utc)
    assert _is_due("not-a-cron", now) is False


def test_is_due_invalid_cron_too_many_fields():
    """Malformed cron with extra fields returns False."""
    now = datetime.now(timezone.utc)
    assert _is_due("* * * * * * *extra", now) is False


def test_is_due_every_minute_naive_datetime():
    """Works with naive datetime (no tzinfo)."""
    now = datetime(2024, 6, 1, 12, 0, 30)
    # Should not raise; may return True or False but not crash
    result = _is_due("* * * * *", now)
    assert isinstance(result, bool)


def test_is_due_yearly_cron_not_due():
    """Yearly cron should not be due at an arbitrary moment."""
    now = datetime(2024, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
    # fires at midnight Jan 1 only
    assert _is_due("0 0 1 1 *", now) is False


# ── start_scheduler / stop_scheduler tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_start_scheduler_creates_task():
    """start_scheduler should create an asyncio Task."""
    import backend.scheduler as sched_module

    # Patch the loop function so it never actually sleeps
    async def mock_loop():
        await asyncio.sleep(3600)

    with patch("backend.scheduler._scheduler_loop", mock_loop):
        start_scheduler()
        try:
            assert sched_module._scheduler_task is not None
            assert isinstance(sched_module._scheduler_task, asyncio.Task)
        finally:
            stop_scheduler()
            # Allow cancellation to propagate
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_stop_scheduler_cancels_task():
    """stop_scheduler should cancel the running task and set it to None."""
    import backend.scheduler as sched_module

    async def mock_loop():
        await asyncio.sleep(3600)

    with patch("backend.scheduler._scheduler_loop", mock_loop):
        start_scheduler()
        task = sched_module._scheduler_task
        assert task is not None

        stop_scheduler()
        await asyncio.sleep(0)

        assert sched_module._scheduler_task is None
        assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_stop_scheduler_when_no_task():
    """stop_scheduler should not raise when no task is running."""
    import backend.scheduler as sched_module
    sched_module._scheduler_task = None
    # Must not raise
    stop_scheduler()


# ── _get_enabled_schedules tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_enabled_schedules_empty():
    """Returns empty list when DB has no enabled schedules."""
    from backend.scheduler import _get_enabled_schedules

    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.database.AsyncSessionLocal", return_value=cm):
        result = await _get_enabled_schedules()

    assert result == []


@pytest.mark.asyncio
async def test_get_enabled_schedules_returns_list():
    """Returns correctly shaped dicts for each enabled schedule."""
    from backend.scheduler import _get_enabled_schedules

    mock_sched = MagicMock()
    mock_sched.id = "sched-1"
    mock_sched.source_id = "src-1"
    mock_sched.cron_expression = "*/5 * * * *"
    mock_sched.parameters = {"limit": 10}

    mock_source = MagicMock()

    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_sched, mock_source)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.database.AsyncSessionLocal", return_value=cm):
        result = await _get_enabled_schedules()

    assert len(result) == 1
    assert result[0]["schedule_id"] == "sched-1"
    assert result[0]["source_id"] == "src-1"
    assert result[0]["cron_expression"] == "*/5 * * * *"
    assert result[0]["parameters"] == {"limit": 10}


# ── _scheduler_loop tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scheduler_loop_fires_due_schedule():
    """_scheduler_loop fires dispatch_scheduled_collection for due schedules."""
    from backend.scheduler import _scheduler_loop

    due_schedule = {
        "schedule_id": "sched-fire",
        "source_id": "src-1",
        "cron_expression": "* * * * *",  # always due
        "parameters": {},
    }

    mock_executor = AsyncMock()
    mock_executor.dispatch_scheduled_collection = AsyncMock()

    iteration = 0

    async def mock_sleep(seconds):
        nonlocal iteration
        iteration += 1
        if iteration >= 2:
            # After first loop iteration, cancel
            raise asyncio.CancelledError()

    with (
        patch("asyncio.sleep", side_effect=mock_sleep),
        patch("backend.scheduler._get_enabled_schedules", new=AsyncMock(return_value=[due_schedule])),
        patch("backend.executor.get_executor", return_value=mock_executor),
    ):
        await _scheduler_loop()

    mock_executor.dispatch_scheduled_collection.assert_called_once_with(
        "sched-fire", "src-1", {}
    )


@pytest.mark.asyncio
async def test_scheduler_loop_skips_non_due_schedule():
    """_scheduler_loop does not fire schedules that aren't due."""
    from backend.scheduler import _scheduler_loop

    non_due_schedule = {
        "schedule_id": "sched-skip",
        "source_id": "src-1",
        "cron_expression": "0 0 1 1 *",  # never due except Jan 1
        "parameters": {},
    }

    mock_executor = AsyncMock()
    mock_executor.dispatch_scheduled_collection = AsyncMock()

    iteration = 0

    async def mock_sleep(seconds):
        nonlocal iteration
        iteration += 1
        if iteration >= 2:
            raise asyncio.CancelledError()

    with (
        patch("asyncio.sleep", side_effect=mock_sleep),
        patch("backend.scheduler._get_enabled_schedules", new=AsyncMock(return_value=[non_due_schedule])),
        patch("backend.executor.get_executor", return_value=mock_executor),
    ):
        await _scheduler_loop()

    mock_executor.dispatch_scheduled_collection.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_loop_handles_exception_and_continues():
    """_scheduler_loop catches non-cancel exceptions and keeps running."""
    from backend.scheduler import _scheduler_loop

    iteration = 0

    async def mock_sleep(seconds):
        nonlocal iteration
        iteration += 1
        if iteration == 1:
            raise RuntimeError("transient error")
        if iteration >= 3:
            raise asyncio.CancelledError()

    with (
        patch("asyncio.sleep", side_effect=mock_sleep),
        patch("backend.scheduler._get_enabled_schedules", new=AsyncMock(return_value=[])),
        patch("backend.executor.get_executor", return_value=AsyncMock()),
    ):
        await _scheduler_loop()

    # Should have run 3 sleep calls (1 error + 2 normal + cancel)
    assert iteration == 3
