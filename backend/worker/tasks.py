"""Celery tasks for async pipeline execution."""

import asyncio
import logging
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
    from backend.pipeline.runner import run_collection_pipeline
    return _run_async(run_collection_pipeline(
        task_id,
        parameters or {},
        celery_task_id=self.request.id,
        worker_id=self.request.hostname,
    ))


@celery_app.task(name="run_scheduled_collection")
def run_scheduled_collection(schedule_id: str, source_id: str, parameters: dict | None = None) -> dict:
    """Create a CollectionTask for a scheduled run, execute pipeline, auto-disable if one-time."""
    from backend.pipeline.runner import run_scheduled_pipeline
    return _run_async(run_scheduled_pipeline(schedule_id, source_id, parameters or {}))


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
