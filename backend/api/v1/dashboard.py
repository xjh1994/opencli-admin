"""Dashboard statistics endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.record import CollectedRecord
from backend.models.source import DataSource
from backend.models.task import CollectionTask, TaskRun
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=ApiResponse[dict])
async def get_stats(db: AsyncSession = Depends(get_db)) -> ApiResponse:
    total_sources = (await db.execute(select(func.count()).select_from(DataSource))).scalar_one()
    enabled_sources = (
        await db.execute(
            select(func.count()).select_from(DataSource).where(DataSource.enabled.is_(True))
        )
    ).scalar_one()

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

    total_records = (
        await db.execute(select(func.count()).select_from(CollectedRecord))
    ).scalar_one()
    ai_processed_records = (
        await db.execute(
            select(func.count())
            .select_from(CollectedRecord)
            .where(CollectedRecord.status == "ai_processed")
        )
    ).scalar_one()

    # Recent task runs (last 10) with task + source info
    recent_runs_result = await db.execute(
        select(TaskRun, CollectionTask, DataSource)
        .join(CollectionTask, TaskRun.task_id == CollectionTask.id)
        .join(DataSource, CollectionTask.source_id == DataSource.id)
        .order_by(TaskRun.created_at.desc())
        .limit(10)
    )
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
