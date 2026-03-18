from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from backend.database import get_db
from backend.models.source import DataSource
from backend.schemas.common import ApiResponse, PaginationMeta
from backend.schemas.task import CollectionTaskRead, TaskRunRead, TaskTriggerRequest
from backend.services import source_service, task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=ApiResponse[list[CollectionTaskRead]])
async def list_tasks(
    source_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tasks, total = await task_service.list_tasks(
        db, source_id=source_id, status=status, page=page, limit=limit
    )
    source_ids = list({t.source_id for t in tasks})
    sources = (await db.execute(select(DataSource).where(DataSource.id.in_(source_ids)))).scalars().all()
    name_map = {s.id: s.name for s in sources}
    data = []
    for t in tasks:
        item = CollectionTaskRead.model_validate(t)
        item.source_name = name_map.get(t.source_id)
        data.append(item)
    return ApiResponse.ok(
        data=data,
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=max(1, -(-total // limit))),
    )


@router.post("/trigger", response_model=ApiResponse[dict], status_code=202)
async def trigger_task(
    body: TaskTriggerRequest, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    source = await source_service.get_source(db, body.source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.enabled:
        raise HTTPException(status_code=400, detail="Source is disabled")

    task = await task_service.create_task(
        db,
        source_id=body.source_id,
        trigger_type="manual",
        parameters=body.parameters,
        priority=body.priority,
    )
    # Commit before dispatching so the background runner's new session can find the task
    await db.commit()

    from backend.executor import get_executor
    result = await get_executor().dispatch_collection(task.id, body.parameters)

    return ApiResponse.ok(result)


@router.get("/{task_id}", response_model=ApiResponse[CollectionTaskRead])
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    task = await task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return ApiResponse.ok(CollectionTaskRead.model_validate(task))


@router.get("/{task_id}/runs", response_model=ApiResponse[list[TaskRunRead]])
async def list_task_runs(
    task_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    task = await task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    runs, total = await task_service.list_task_runs(db, task_id, page=page, limit=limit)
    return ApiResponse.ok(
        data=[TaskRunRead.model_validate(r) for r in runs],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=max(1, -(-total // limit))),
    )
