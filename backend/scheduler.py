"""Local async scheduler — replaces Celery Beat when TASK_EXECUTOR=local."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from croniter import croniter

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def _get_enabled_schedules() -> list[dict]:
    from sqlalchemy import select
    from backend.database import AsyncSessionLocal
    from backend.models.schedule import CronSchedule
    from backend.models.source import DataSource

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CronSchedule, DataSource)
            .join(DataSource, CronSchedule.source_id == DataSource.id)
            .where(CronSchedule.enabled.is_(True), DataSource.enabled.is_(True))
        )
        return [
            {
                "schedule_id": sched.id,
                "source_id": sched.source_id,
                "cron_expression": sched.cron_expression,
                "parameters": sched.parameters,
            }
            for sched, _ in result.all()
        ]


def _is_due(cron_expression: str, now: datetime) -> bool:
    """Return True if cron fired within the last 60 seconds."""
    try:
        base = now - timedelta(seconds=61)
        cron = croniter(cron_expression, base)
        next_fire = cron.get_next(datetime)
        return next_fire <= now
    except Exception:
        return False


async def _scheduler_loop() -> None:
    logger.info("Local scheduler started")
    while True:
        try:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)
            schedules = await _get_enabled_schedules()
            from backend.executor import get_executor
            executor = get_executor()
            for sched in schedules:
                if _is_due(sched["cron_expression"], now):
                    logger.info("Firing schedule %s", sched["schedule_id"])
                    await executor.dispatch_scheduled_collection(
                        sched["schedule_id"],
                        sched["source_id"],
                        sched["parameters"],
                    )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Scheduler loop error: %s", exc)

    logger.info("Local scheduler stopped")


def start_scheduler() -> None:
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())


def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
