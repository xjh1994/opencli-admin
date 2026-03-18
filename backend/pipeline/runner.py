"""Shared pipeline runner — used by both local executor and Celery tasks."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.task import CollectionTask, TaskRun
from backend.pipeline.pipeline import run_pipeline

logger = logging.getLogger(__name__)


async def run_collection_pipeline(
    task_id: str,
    parameters: dict,
    celery_task_id: str | None = None,
    worker_id: str | None = None,
) -> dict:
    """Execute full collection pipeline for task_id. Returns result dict."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CollectionTask).where(CollectionTask.id == task_id)
        )
        collection_task = result.scalar_one_or_none()
        if not collection_task:
            return {"error": f"Task {task_id} not found"}

        run = TaskRun(
            task_id=task_id,
            status="running",
            celery_task_id=celery_task_id,
            worker_id=worker_id,
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.flush()

        collection_task.status = "running"
        await session.flush()

        from backend.models.source import DataSource
        src_result = await session.execute(
            select(DataSource).where(DataSource.id == collection_task.source_id)
        )
        source = src_result.scalar_one_or_none()
        if not source:
            run.status = "failed"
            run.error_message = "Source not found"
            collection_task.status = "failed"
            collection_task.error_message = "Source not found"
            await session.commit()
            return {"error": "Source not found"}

        merged_params = {**collection_task.parameters, **parameters}

        # Load agent config if task has an agent_id
        agent_config = None
        if collection_task.agent_id:
            from backend.models.agent import AIAgent
            agent_res = await session.execute(
                select(AIAgent).where(AIAgent.id == collection_task.agent_id)
            )
            agent = agent_res.scalar_one_or_none()
            if agent and agent.enabled:
                agent_config = {
                    "processor_type": agent.processor_type,
                    "model": agent.model,
                    "prompt_template": agent.prompt_template,
                    **agent.processor_config,
                }

        pipeline_result = await run_pipeline(
            session, source, task_id, merged_params, agent_config=agent_config
        )

        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = pipeline_result.duration_ms
        run.records_collected = pipeline_result.stored

        if pipeline_result.success:
            run.status = "completed"
            collection_task.status = "completed"
            collection_task.error_message = None
        else:
            run.status = "failed"
            run.error_message = pipeline_result.error
            collection_task.status = "failed"
            collection_task.error_message = pipeline_result.error

        await session.commit()

        return {
            "task_id": task_id,
            "run_id": run.id,
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
        is_one_time = False
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
