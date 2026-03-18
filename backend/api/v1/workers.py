from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/workers", tags=["workers"])


def _inspect_workers() -> tuple[dict, dict]:
    from backend.worker.celery_app import celery_app
    inspect = celery_app.control.inspect(timeout=3)
    return inspect.stats() or {}, inspect.active() or {}


@router.get("", response_model=ApiResponse[list[dict]])
async def list_workers(db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """Return live Celery worker nodes derived from broker inspect."""
    try:
        stats, active = _inspect_workers()
        workers = []
        for worker_id, info in stats.items():
            active_tasks = len(active.get(worker_id, []))
            workers.append({
                "id": worker_id,
                "worker_id": worker_id,
                "hostname": info.get("hostname", worker_id),
                "status": "online",
                "active_tasks": active_tasks,
                "last_heartbeat": None,
                "concurrency": info.get("pool", {}).get("max-concurrency"),
                "celery_version": info.get("versions", {}).get("celery"),
            })
        return ApiResponse.ok(workers)
    except Exception as exc:
        return ApiResponse.ok([])


@router.get("/celery-stats", response_model=ApiResponse[dict])
async def celery_stats() -> ApiResponse:
    """Query live Celery worker stats via inspect."""
    try:
        stats, active = _inspect_workers()
        return ApiResponse.ok({"stats": stats, "active": active})
    except Exception as exc:
        return ApiResponse.ok({"error": str(exc), "stats": {}, "active": {}})
