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

    # Recent task runs (last 10)
    recent_runs_result = await db.execute(
        select(TaskRun).order_by(TaskRun.created_at.desc()).limit(10)
    )
    recent_runs = recent_runs_result.scalars().all()

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
                    "id": r.id,
                    "task_id": r.task_id,
                    "status": r.status,
                    "records_collected": r.records_collected,
                    "duration_ms": r.duration_ms,
                    "created_at": r.created_at.isoformat(),
                }
                for r in recent_runs
            ],
        }
    )
