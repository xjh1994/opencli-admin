"""Unit tests for backend/pipeline/runner.py — run_collection_pipeline and run_scheduled_pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipeline.runner import run_collection_pipeline, run_scheduled_pipeline


def make_session_cm(session):
    """Create an async context manager that yields the given session."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_task(task_id="task-1", source_id="src-1"):
    task = MagicMock()
    task.id = task_id
    task.source_id = source_id
    task.parameters = {}
    task.agent_id = None
    task.status = "pending"
    task.error_message = None
    return task


def _make_source(source_id="src-1"):
    source = MagicMock()
    source.id = source_id
    source.name = "Test Source"
    source.channel_type = "rss"
    source.channel_config = {"feed_url": "https://example.com/rss"}
    return source


def _make_run(run_id="run-1"):
    run = MagicMock()
    run.id = run_id
    run.status = "running"
    run.error_message = None
    return run


def _make_pipeline_result(success=True, error=None):
    result = MagicMock()
    result.success = success
    result.error = error
    result.collected = 5
    result.stored = 4
    result.skipped = 1
    result.ai_processed = 0
    result.duration_ms = 100
    return result


# ── task not found ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_pipeline_task_not_found():
    """Returns error dict when task_id does not exist in the DB."""
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch("backend.pipeline.runner.AsyncSessionLocal", return_value=make_session_cm(mock_session)):
        result = await run_collection_pipeline("nonexistent-task", {})

    assert "error" in result
    assert "not found" in result["error"].lower()


# ── source not found after phase 1 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_pipeline_source_not_found():
    """Returns error dict when source_id from task does not exist."""
    task = _make_task()
    run = _make_run()

    # Phase 1 session: returns task
    session1 = AsyncMock()
    session1.get = AsyncMock(side_effect=lambda model, id: task if "Task" in str(model) else None)
    session1.add = MagicMock()
    session1.flush = AsyncMock()
    session1.commit = AsyncMock()

    # Attach run id after flush
    async def flush1():
        run.id = "run-1"

    session1.flush = AsyncMock(side_effect=flush1)

    # Simulate flush setting run.id by making add() capture the run object
    added_run = None

    def capture_add(obj):
        nonlocal added_run
        added_run = obj
        obj.id = "run-1"

    session1.add = MagicMock(side_effect=capture_add)
    session1.flush = AsyncMock()
    session1.commit = AsyncMock()

    # Phase 1: get returns task
    session1.get = AsyncMock(return_value=task)

    # Phase 2 session: source not found
    session2 = AsyncMock()
    session2.get = AsyncMock(return_value=None)  # source not found

    # Phase 2b error-recording session
    session2b = AsyncMock()
    session2b.get = AsyncMock(return_value=None)
    session2b.commit = AsyncMock()

    with patch(
        "backend.pipeline.runner.AsyncSessionLocal",
        side_effect=[
            make_session_cm(session1),
            make_session_cm(session2),
            make_session_cm(session2b),
        ],
    ):
        result = await run_collection_pipeline("task-1", {})

    assert "error" in result
    assert "source not found" in result["error"].lower()


# ── successful pipeline execution ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_pipeline_success():
    """Full successful pipeline returns result dict with expected keys."""
    task = _make_task()
    source = _make_source()
    run = _make_run()
    pipeline_result = _make_pipeline_result(success=True)

    # Phase 1 session
    session1 = AsyncMock()

    def p1_get(model, id):
        return task

    session1.get = AsyncMock(side_effect=p1_get)

    def capture_add(obj):
        obj.id = "run-1"

    session1.add = MagicMock(side_effect=capture_add)
    session1.flush = AsyncMock()
    session1.commit = AsyncMock()

    # Phase 2 session: source found
    session2 = AsyncMock()

    def p2_get(model, id):
        return source

    session2.get = AsyncMock(side_effect=p2_get)
    session2.expunge = MagicMock()

    # Phase 4 session: finalize
    session4 = AsyncMock()
    session4.get = AsyncMock(side_effect=lambda model, id: task if id == "task-1" else run)
    session4.commit = AsyncMock()

    with patch(
        "backend.pipeline.runner.AsyncSessionLocal",
        side_effect=[
            make_session_cm(session1),
            make_session_cm(session2),
            make_session_cm(session4),
        ],
    ):
        with patch(
            "backend.pipeline.runner.run_pipeline",
            new_callable=AsyncMock,
            return_value=pipeline_result,
        ):
            result = await run_collection_pipeline("task-1", {})

    assert result.get("success") is True
    assert result.get("task_id") == "task-1"
    assert "run_id" in result
    assert result.get("stored") == 4
    assert result.get("skipped") == 1


# ── failed pipeline execution ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_pipeline_failure_recorded():
    """When pipeline fails, result dict has success=False and error message."""
    task = _make_task()
    source = _make_source()
    pipeline_result = _make_pipeline_result(success=False, error="collection failed")

    session1 = AsyncMock()

    def capture_add(obj):
        obj.id = "run-1"

    session1.add = MagicMock(side_effect=capture_add)
    session1.get = AsyncMock(return_value=task)
    session1.flush = AsyncMock()
    session1.commit = AsyncMock()

    session2 = AsyncMock()
    session2.get = AsyncMock(return_value=source)
    session2.expunge = MagicMock()

    session4 = AsyncMock()
    session4.get = AsyncMock(return_value=task)
    session4.commit = AsyncMock()

    with patch(
        "backend.pipeline.runner.AsyncSessionLocal",
        side_effect=[
            make_session_cm(session1),
            make_session_cm(session2),
            make_session_cm(session4),
        ],
    ):
        with patch(
            "backend.pipeline.runner.run_pipeline",
            new_callable=AsyncMock,
            return_value=pipeline_result,
        ):
            result = await run_collection_pipeline("task-1", {})

    assert result.get("success") is False
    assert result.get("error") == "collection failed"


# ── run_scheduled_pipeline ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_scheduled_pipeline_success():
    """run_scheduled_pipeline creates a task, runs pipeline, and returns outcome."""
    from backend.pipeline.runner import run_scheduled_pipeline

    task = _make_task()
    source = _make_source()
    pipeline_result = _make_pipeline_result(success=True)

    # Mock schedule object
    mock_schedule = MagicMock()
    mock_schedule.agent_id = None
    mock_schedule.last_run_at = None
    mock_schedule.is_one_time = False

    # Mock scalar result
    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar_one_or_none = MagicMock(return_value=mock_schedule)

    # Phase 1: create task session
    session1 = AsyncMock()
    session1.execute = AsyncMock(return_value=mock_scalar_result)
    session1.commit = AsyncMock()

    # Mock task_service.create_task
    task.id = "task-sched-1"

    # Phase 2: run_collection_pipeline is mocked entirely
    with patch("backend.pipeline.runner.AsyncSessionLocal",
               return_value=make_session_cm(session1)):
        with patch("backend.services.task_service.create_task",
                   new_callable=AsyncMock, return_value=task):
            with patch("backend.pipeline.runner.run_collection_pipeline",
                       new_callable=AsyncMock, return_value={"success": True, "task_id": "task-sched-1"}):
                result = await run_scheduled_pipeline("sched-1", "src-1", {})

    assert result.get("success") is True


@pytest.mark.asyncio
async def test_run_scheduled_pipeline_one_time_disables_schedule():
    """One-time schedule is disabled after execution."""
    from backend.pipeline.runner import run_scheduled_pipeline

    task = _make_task()
    task.id = "task-sched-2"

    mock_schedule = MagicMock()
    mock_schedule.agent_id = None
    mock_schedule.last_run_at = None
    mock_schedule.is_one_time = True
    mock_schedule.enabled = True

    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar_one_or_none = MagicMock(return_value=mock_schedule)

    # Session for creating task and marking last_run_at
    session1 = AsyncMock()
    session1.execute = AsyncMock(return_value=mock_scalar_result)
    session1.commit = AsyncMock()

    # Session for disabling one-time schedule
    session2 = AsyncMock()
    mock_scalar_disable = MagicMock()
    mock_schedule_copy = MagicMock()
    mock_schedule_copy.enabled = True
    mock_scalar_disable.scalar_one_or_none = MagicMock(return_value=mock_schedule_copy)
    session2.execute = AsyncMock(return_value=mock_scalar_disable)
    session2.commit = AsyncMock()

    sessions = [session1, session2]

    with patch("backend.pipeline.runner.AsyncSessionLocal",
               side_effect=[make_session_cm(s) for s in sessions]):
        with patch("backend.services.task_service.create_task",
                   new_callable=AsyncMock, return_value=task):
            with patch("backend.pipeline.runner.run_collection_pipeline",
                       new_callable=AsyncMock, return_value={"success": True}):
                result = await run_scheduled_pipeline("sched-2", "src-1", {})

    # One-time schedule should have been disabled
    assert mock_schedule_copy.enabled is False


@pytest.mark.asyncio
async def test_run_pipeline_source_not_found_marks_task_and_run():
    """When source not found, task and run records are marked failed (lines 66-70)."""
    task = _make_task()
    run = _make_run()

    added_run = run

    def capture_add(obj):
        obj.id = "run-1"

    # Phase 1: task exists → run created
    session1 = AsyncMock()
    session1.get = AsyncMock(return_value=task)
    session1.add = MagicMock(side_effect=capture_add)
    session1.flush = AsyncMock()
    session1.commit = AsyncMock()

    # Phase 2: source not found
    session2 = AsyncMock()
    session2.get = AsyncMock(return_value=None)

    # Phase 2b error-recording session: task and run both found
    error_task = _make_task()
    error_run = _make_run()

    from backend.models.task import CollectionTask as _CollectionTask

    def get_task_or_run(model, obj_id):
        if model is _CollectionTask:
            return error_task
        return error_run

    session2b = AsyncMock()
    session2b.get = AsyncMock(side_effect=get_task_or_run)
    session2b.commit = AsyncMock()

    with patch(
        "backend.pipeline.runner.AsyncSessionLocal",
        side_effect=[
            make_session_cm(session1),
            make_session_cm(session2),
            make_session_cm(session2b),
        ],
    ):
        result = await run_collection_pipeline("task-1", {})

    assert result == {"error": "Source not found"}
    assert error_task.status == "failed"
    assert error_task.error_message == "Source not found"
    assert error_run.status == "failed"


@pytest.mark.asyncio
async def test_run_pipeline_with_agent_id():
    """agent_id triggers agent config loading including provider credentials."""
    task = _make_task()
    task.agent_id = "agent-1"
    run = _make_run()

    def capture_add(obj):
        obj.id = "run-1"

    session1 = AsyncMock()
    session1.get = AsyncMock(return_value=task)
    session1.add = MagicMock(side_effect=capture_add)
    session1.flush = AsyncMock()
    session1.commit = AsyncMock()

    source = _make_source()
    mock_agent = MagicMock()
    mock_agent.enabled = True
    mock_agent.provider_id = "prov-1"
    mock_agent.processor_type = "claude"
    mock_agent.model = "claude-3-haiku"
    mock_agent.prompt_template = "Summarize: {{content}}"
    mock_agent.processor_config = {}

    mock_provider = MagicMock()
    mock_provider.enabled = True
    mock_provider.api_key = "sk-test-123"
    mock_provider.base_url = "https://api.example.com"

    def phase2_get(model, obj_id):
        if "DataSource" in str(model):
            return source
        if "AIAgent" in str(model):
            return mock_agent
        if "ModelProvider" in str(model):
            return mock_provider
        return None

    session2 = AsyncMock()
    session2.get = AsyncMock(side_effect=phase2_get)
    session2.expunge = MagicMock()

    # Phase 3+4 sessions for pipeline execution and final status
    session3 = AsyncMock()
    session3.get = AsyncMock(return_value=run)
    session3.commit = AsyncMock()

    pipeline_result = _make_pipeline_result(success=True)

    with patch(
        "backend.pipeline.runner.AsyncSessionLocal",
        side_effect=[make_session_cm(session1), make_session_cm(session2), make_session_cm(session3)],
    ):
        with patch("backend.pipeline.runner.run_pipeline", new_callable=AsyncMock, return_value=pipeline_result):
            result = await run_collection_pipeline("task-1", {})

    assert result["success"] is True
