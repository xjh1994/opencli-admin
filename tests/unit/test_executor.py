"""Unit tests for backend executor modules."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── LocalExecutor ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_local_executor_dispatch_collection():
    """dispatch_collection creates an asyncio Task and returns task_id."""
    from backend.executor.local import LocalExecutor

    executor = LocalExecutor()

    with patch("backend.pipeline.runner.run_collection_pipeline", new=AsyncMock(return_value={})):
        result = await executor.dispatch_collection("task-123", {"limit": 5})

    assert result["task_id"] == "task-123"
    # Allow background task to finish
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_local_executor_dispatch_scheduled_collection():
    """dispatch_scheduled_collection creates an asyncio Task (no return value)."""
    from backend.executor.local import LocalExecutor

    executor = LocalExecutor()

    with patch("backend.pipeline.runner.run_scheduled_pipeline", new=AsyncMock(return_value={})):
        await executor.dispatch_scheduled_collection("sched-1", "src-1", {})

    # Allow background task to complete
    await asyncio.sleep(0)


def test_log_task_exception_logs_error():
    """_log_task_exception logs when task has an unhandled exception."""
    from backend.executor.local import _log_task_exception

    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = RuntimeError("task error")

    # Should not raise
    with patch("backend.executor.local.logger") as mock_logger:
        _log_task_exception(task)
        mock_logger.exception.assert_called_once()


def test_log_task_exception_skips_cancelled():
    """_log_task_exception does nothing for cancelled tasks."""
    from backend.executor.local import _log_task_exception

    task = MagicMock()
    task.cancelled.return_value = True

    with patch("backend.executor.local.logger") as mock_logger:
        _log_task_exception(task)
        mock_logger.exception.assert_not_called()


def test_log_task_exception_skips_no_exception():
    """_log_task_exception does nothing when task has no exception."""
    from backend.executor.local import _log_task_exception

    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = None

    with patch("backend.executor.local.logger") as mock_logger:
        _log_task_exception(task)
        mock_logger.exception.assert_not_called()


# ── get_executor ───────────────────────────────────────────────────────────────

def test_get_executor_returns_local_executor():
    """get_executor returns LocalExecutor when task_executor=local."""
    from backend.executor import get_executor
    from backend.executor.local import LocalExecutor

    # Clear lru_cache to get fresh executor
    get_executor.cache_clear()

    with patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value.task_executor = "local"
        executor = get_executor()

    assert isinstance(executor, LocalExecutor)
    get_executor.cache_clear()


# ── CeleryExecutor ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_celery_executor_dispatch_collection():
    """CeleryExecutor.dispatch_collection calls apply_async and returns task_id."""
    from backend.executor.celery_exec import CeleryExecutor

    executor = CeleryExecutor()

    mock_result = MagicMock()
    mock_result.id = "celery-task-abc"

    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(return_value=mock_result)

    with patch("backend.worker.tasks.run_collection", mock_task):
        result = await executor.dispatch_collection("task-999", {"p": 1})

    assert result["task_id"] == "task-999"
    assert result["celery_task_id"] == "celery-task-abc"
    mock_task.apply_async.assert_called_once_with(
        kwargs={"task_id": "task-999", "parameters": {"p": 1}}
    )


@pytest.mark.asyncio
async def test_celery_executor_dispatch_scheduled_collection():
    """CeleryExecutor.dispatch_scheduled_collection calls apply_async."""
    from backend.executor.celery_exec import CeleryExecutor

    executor = CeleryExecutor()

    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(return_value=MagicMock())

    with patch("backend.worker.tasks.run_scheduled_collection", mock_task):
        await executor.dispatch_scheduled_collection("sched-1", "src-1", {"k": "v"})

    mock_task.apply_async.assert_called_once_with(
        kwargs={"schedule_id": "sched-1", "source_id": "src-1", "parameters": {"k": "v"}}
    )
