"""Shared pipeline runner — used by both local executor and Celery tasks."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.task import CollectionTask, TaskRun
from backend.pipeline import events
from backend.pipeline.pipeline import run_pipeline

logger = logging.getLogger(__name__)


async def run_collection_pipeline(
    task_id: str,
    parameters: dict,
    celery_task_id: str | None = None,
    worker_id: str | None = None,
) -> dict:
    """Execute full collection pipeline for task_id.

    Uses separate short-lived sessions per write phase to avoid holding an open
    write transaction during the long-running collection step (Chrome/CLI).
    """
    logger.info("[task:%s] pipeline start | params=%s", task_id, parameters)

    # ── Phase 1: mark running, create TaskRun ────────────────────────────────
    run_id: str | None = None
    source_id: str | None = None
    merged_params: dict = {}
    agent_id: str | None = None
    trigger_type: str = "manual"

    async with AsyncSessionLocal() as session:
        task = await session.get(CollectionTask, task_id)
        if not task:
            return {"error": f"Task {task_id} not found"}

        run = TaskRun(
            task_id=task_id,
            status="running",
            celery_task_id=celery_task_id,
            worker_id=worker_id,
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        task.status = "running"
        await session.flush()
        run_id = run.id
        source_id = task.source_id
        merged_params = {**task.parameters, **parameters}
        agent_id = task.agent_id
        trigger_type = task.trigger_type
        await session.commit()

    # Emit trigger event after committing the run row
    if run_id and source_id:
        await events.emit(
            run_id, "trigger",
            f"任务触发 | 方式={trigger_type} 数据源ID={source_id}",
            detail={"trigger_type": trigger_type, "source_id": source_id},
        )

    logger.info("[task:%s] phase1 done | run_id=%s source_id=%s merged_params=%s",
                task_id, run_id, source_id, merged_params)

    # ── Phase 2: load source + agent config (read-only, no write lock) ───────
    from backend.models.source import DataSource
    async with AsyncSessionLocal() as session:
        source = await session.get(DataSource, source_id)
        if not source:
            async with AsyncSessionLocal() as s2:
                t = await s2.get(CollectionTask, task_id)
                r = await s2.get(TaskRun, run_id)
                if t:
                    t.status = "failed"
                    t.error_message = "Source not found"
                if r:
                    r.status = "failed"
                    r.error_message = "Source not found"
                await s2.commit()
            return {"error": "Source not found"}

        agent_config = None
        if agent_id:
            from backend.models.agent import AIAgent
            from backend.models.provider import ModelProvider
            agent = await session.get(AIAgent, agent_id)
            if agent and agent.enabled:
                # Start with provider credentials (if linked), then overlay agent's own config
                provider_config: dict = {}
                if agent.provider_id:
                    provider = await session.get(ModelProvider, agent.provider_id)
                    if provider and provider.enabled:
                        if provider.api_key:
                            provider_config["api_key"] = provider.api_key
                        if provider.base_url:
                            provider_config["base_url"] = provider.base_url
                agent_config = {
                    "processor_type": agent.processor_type,
                    "model": agent.model,
                    "prompt_template": agent.prompt_template,
                    **provider_config,
                    **agent.processor_config,  # agent-level overrides provider
                }
        # Detach source from session so it can be used after session closes
        session.expunge(source)
    logger.info("[task:%s] phase2 done | source=%s channel=%s agent_config=%s",
                task_id, source.name, source.channel_type,
                {k: v for k, v in (agent_config or {}).items() if k != "prompt_template"})

    # ── Phase 3: run pipeline (no session held during collection) ─────────────
    pipeline_result = await run_pipeline(
        task_id=task_id,
        source=source,
        parameters=merged_params,
        agent_config=agent_config,
        run_id=run_id,
    )

    # ── Phase 4: persist final status ────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        task = await session.get(CollectionTask, task_id)
        run = await session.get(TaskRun, run_id)

        if run:
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = pipeline_result.duration_ms
            run.records_collected = pipeline_result.stored
            if pipeline_result.metadata.get("node_url"):
                run.node_url = pipeline_result.metadata["node_url"]

        if pipeline_result.success:
            if task:
                task.status = "completed"
                task.error_message = None
            if run:
                run.status = "completed"
        else:
            if task:
                task.status = "failed"
                task.error_message = pipeline_result.error
            if run:
                run.status = "failed"
                run.error_message = pipeline_result.error

        await session.commit()

    logger.info(
        "[task:%s] pipeline done | success=%s collected=%d stored=%d skipped=%d "
        "ai=%d duration_ms=%d error=%s",
        task_id, pipeline_result.success, pipeline_result.collected,
        pipeline_result.stored, pipeline_result.skipped,
        pipeline_result.ai_processed, pipeline_result.duration_ms,
        pipeline_result.error,
    )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "success": pipeline_result.success,
        "collected": pipeline_result.collected,
        "stored": pipeline_result.stored,
        "skipped": pipeline_result.skipped,
        "error": pipeline_result.error,
    }


async def run_scheduled_pipeline(
    schedule_id: str,
    source_id: str,
    parameters: dict,
) -> dict:
    """Create CollectionTask for a scheduled run, run pipeline, auto-disable if one-time."""
    from backend.models.schedule import CronSchedule
    from backend.services import task_service

    is_one_time = False
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CronSchedule).where(CronSchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        schedule_agent_id = schedule.agent_id if schedule else None

        task = await task_service.create_task(
            session,
            source_id=source_id,
            trigger_type="scheduled",
            parameters=parameters,
            agent_id=schedule_agent_id,
        )
        if schedule:
            schedule.last_run_at = datetime.now(timezone.utc)
            is_one_time = schedule.is_one_time
        await session.commit()
        task_id = task.id

    outcome = await run_collection_pipeline(task_id, parameters)

    if is_one_time:
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(CronSchedule).where(CronSchedule.id == schedule_id)
            )
            sched = res.scalar_one_or_none()
            if sched:
                sched.enabled = False
                await session.commit()

    return outcome
