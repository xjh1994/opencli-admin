"""Dashboard statistics endpoint."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.record import CollectedRecord
from backend.models.source import DataSource
from backend.models.task import CollectionTask, TaskRun
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _parse_time_range(
    range: str,
    start: Optional[datetime],
    end: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Return (since, until) UTC datetimes for the given range string."""
    now = datetime.now(timezone.utc)
    if range == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return since, None
    if range == "yesterday":
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since = today_start - timedelta(days=1)
        return since, today_start
    if range == "7d":
        return now - timedelta(days=7), None
    if range == "30d":
        return now - timedelta(days=30), None
    if range == "custom":
        return start, end
    return None, None  # "all"


@router.get("/stats", response_model=ApiResponse[dict])
async def get_stats(
    range: str = Query("all", description="Time range: all | today | yesterday | 7d | 30d | custom"),
    start: Optional[datetime] = Query(None, description="Custom range start (ISO 8601, UTC)"),
    end: Optional[datetime] = Query(None, description="Custom range end (ISO 8601, UTC)"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    since, until = _parse_time_range(range, start, end)

    # ── Source counts (not time-filtered — these are global config) ───────────
    total_sources = (await db.execute(select(func.count()).select_from(DataSource))).scalar_one()
    enabled_sources = (
        await db.execute(
            select(func.count()).select_from(DataSource).where(DataSource.enabled.is_(True))
        )
    ).scalar_one()

    # ── Task counts (based on CollectionTask status — global) ─────────────────
    total_tasks = (await db.execute(select(func.count()).select_from(CollectionTask))).scalar_one()
    running_tasks = (
        await db.execute(
            select(func.count())
            .select_from(CollectionTask)
            .where(CollectionTask.status == "running")
        )
    ).scalar_one()
    failed_tasks = (
        await db.execute(
            select(func.count())
            .select_from(CollectionTask)
            .where(CollectionTask.status == "failed")
        )
    ).scalar_one()

    # ── TaskRun counts (time-filtered) ────────────────────────────────────────
    run_q = select(func.count()).select_from(TaskRun)
    if since:
        run_q = run_q.where(TaskRun.created_at >= since)
    if until:
        run_q = run_q.where(TaskRun.created_at < until)

    run_success_q = run_q.where(TaskRun.status == "completed")
    run_failed_q = run_q.where(TaskRun.status == "failed")

    run_success = (await db.execute(run_success_q)).scalar_one()
    run_failed = (await db.execute(run_failed_q)).scalar_one()
    run_total = run_success + run_failed + (
        await db.execute(run_q.where(TaskRun.status == "running"))
    ).scalar_one()

    # ── Record counts (time-filtered) ─────────────────────────────────────────
    rec_q = select(func.count()).select_from(CollectedRecord)
    if since:
        rec_q = rec_q.where(CollectedRecord.created_at >= since)
    if until:
        rec_q = rec_q.where(CollectedRecord.created_at < until)

    total_records = (await db.execute(rec_q)).scalar_one()
    ai_processed_records = (
        await db.execute(rec_q.where(CollectedRecord.status == "ai_processed"))
    ).scalar_one()

    # ── Recent task runs (time-filtered, last 10) ─────────────────────────────
    recent_q = (
        select(TaskRun, CollectionTask, DataSource)
        .join(CollectionTask, TaskRun.task_id == CollectionTask.id)
        .join(DataSource, CollectionTask.source_id == DataSource.id)
        .order_by(TaskRun.created_at.desc())
        .limit(10)
    )
    if since:
        recent_q = recent_q.where(TaskRun.created_at >= since)
    if until:
        recent_q = recent_q.where(TaskRun.created_at < until)

    recent_runs_result = await db.execute(recent_q)
    recent_runs = recent_runs_result.all()

    return ApiResponse.ok(
        {
            "sources": {
                "total": total_sources,
                "enabled": enabled_sources,
                "disabled": total_sources - enabled_sources,
            },
            "tasks": {
                "total": total_tasks,
                "running": running_tasks,
                "failed": failed_tasks,
            },
            "runs": {
                "total": run_total,
                "success": run_success,
                "failed": run_failed,
                "success_rate": round(run_success / run_total * 100, 1) if run_total > 0 else 0.0,
            },
            "records": {
                "total": total_records,
                "ai_processed": ai_processed_records,
            },
            "recent_runs": [
                {
                    "id": run.id,
                    "task_id": run.task_id,
                    "task_trigger_type": task.trigger_type,
                    "source_name": source.name,
                    "status": run.status,
                    "records_collected": run.records_collected,
                    "duration_ms": run.duration_ms,
                    "created_at": run.created_at.isoformat(),
                }
                for run, task, source in recent_runs
            ],
        }
    )
