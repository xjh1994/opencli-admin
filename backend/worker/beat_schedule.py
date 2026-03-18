"""Celery Beat scheduler that reads cron schedules from the database."""

import asyncio
import logging
from datetime import datetime, timezone

from celery.schedules import crontab

logger = logging.getLogger(__name__)


async def _get_enabled_schedules() -> list[dict]:
    """Fetch enabled cron schedules with their sources."""
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
        rows = result.all()
        return [
            {
                "schedule_id": sched.id,
                "source_id": sched.source_id,
                "name": sched.name,
                "cron_expression": sched.cron_expression,
                "parameters": sched.parameters,
            }
            for sched, _ in rows
        ]


def parse_cron_expression(expr: str) -> crontab:
    """Parse a 5-field cron expression into Celery crontab."""
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression (need 5 fields): {expr!r}")
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


def build_beat_schedule() -> dict:
    """Build Celery beat_schedule dict from DB schedules (sync wrapper)."""
    loop = asyncio.new_event_loop()
    try:
        schedules = loop.run_until_complete(_get_enabled_schedules())
    except Exception as exc:
        logger.warning("Could not load DB schedules for beat: %s", exc)
        return {}
    finally:
        loop.close()

    beat_schedule: dict = {}
    for sched in schedules:
        try:
            schedule_key = f"schedule-{sched['schedule_id']}"
            beat_schedule[schedule_key] = {
                "task": "run_scheduled_collection",
                "schedule": parse_cron_expression(sched["cron_expression"]),
                "args": [],
                "kwargs": {
                    "schedule_id": sched["schedule_id"],
                    "source_id": sched["source_id"],
                    "parameters": sched["parameters"],
                },
            }
        except Exception as exc:
            logger.warning("Skipping invalid schedule %s: %s", sched.get("name"), exc)

    return beat_schedule
