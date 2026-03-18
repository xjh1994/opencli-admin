"""Celery tasks for async pipeline execution."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from celery import Task

from backend.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine in a Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="run_collection", max_retries=3, default_retry_delay=60)
def run_collection(self: Task, task_id: str, parameters: dict | None = None) -> dict:
    """Execute the full collection pipeline for a task."""
    return _run_async(_run_collection_async(self, task_id, parameters or {}))


async def _run_collection_async(task: Task, task_id: str, parameters: dict) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from backend.database import AsyncSessionLocal
    from backend.models.task import CollectionTask, TaskRun
    from backend.pipeline.pipeline import run_pipeline

    async with AsyncSessionLocal() as session:
        # Load task + source
        result = await session.execute(
            select(CollectionTask).where(CollectionTask.id == task_id)
        )
        collection_task = result.scalar_one_or_none()
        if not collection_task:
            return {"error": f"Task {task_id} not found"}

        # Create a TaskRun record
        run = TaskRun(
            task_id=task_id,
            status="running",
            celery_task_id=task.request.id,
            worker_id=task.request.hostname,
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.flush()

        # Update task status
        collection_task.status = "running"
        await session.flush()

        # Load source
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
        pipeline_result = await run_pipeline(session, source, task_id, merged_params)

        # Update run record
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


@celery_app.task(name="send_notification")
def send_notification(rule_id: str, record_id: str) -> dict:
    """Send a single notification for a rule/record pair."""
    return _run_async(_send_notification_async(rule_id, record_id))


async def _send_notification_async(rule_id: str, record_id: str) -> dict:
    from sqlalchemy import select

    from backend.database import AsyncSessionLocal
    from backend.models.notification import NotificationRule
    from backend.models.record import CollectedRecord
    from backend.notifiers.base import NotificationPayload
    from backend.notifiers.registry import get_notifier

    async with AsyncSessionLocal() as session:
        rule_result = await session.execute(
            select(NotificationRule).where(NotificationRule.id == rule_id)
        )
        rule = rule_result.scalar_one_or_none()
        if not rule:
            return {"error": f"Rule {rule_id} not found"}

        record_result = await session.execute(
            select(CollectedRecord).where(CollectedRecord.id == record_id)
        )
        record = record_result.scalar_one_or_none()
        if not record:
            return {"error": f"Record {record_id} not found"}

        notifier = get_notifier(rule.notifier_type)
        payload = NotificationPayload(
            event=rule.trigger_event,
            source_id=record.source_id,
            record_id=record.id,
            data=record.normalized_data,
            ai_enrichment=record.ai_enrichment,
        )
        success = await notifier.send(rule.notifier_config, payload)
        return {"success": success, "rule_id": rule_id, "record_id": record_id}
