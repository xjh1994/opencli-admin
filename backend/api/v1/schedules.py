from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ApiResponse, PaginationMeta
from backend.schemas.schedule import CronScheduleCreate, CronScheduleRead, CronScheduleUpdate
from backend.services import schedule_service

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=ApiResponse[list[CronScheduleRead]])
async def list_schedules(
    source_id: Optional[str] = None,
    enabled: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    schedules, total = await schedule_service.list_schedules(
        db, source_id=source_id, enabled=enabled, page=page, limit=limit
    )
    return ApiResponse.ok(
        data=[CronScheduleRead.model_validate(s) for s in schedules],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=max(1, -(-total // limit))),
    )


@router.post("", response_model=ApiResponse[CronScheduleRead], status_code=201)
async def create_schedule(
    body: CronScheduleCreate, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    if not schedule_service.validate_cron_expression(body.cron_expression):
        raise HTTPException(status_code=422, detail="Invalid cron expression")
    schedule = await schedule_service.create_schedule(db, body)
    return ApiResponse.ok(CronScheduleRead.model_validate(schedule))


@router.get("/{schedule_id}", response_model=ApiResponse[CronScheduleRead])
async def get_schedule(
    schedule_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    schedule = await schedule_service.get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ApiResponse.ok(CronScheduleRead.model_validate(schedule))


@router.patch("/{schedule_id}", response_model=ApiResponse[CronScheduleRead])
async def update_schedule(
    schedule_id: str, body: CronScheduleUpdate, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    schedule = await schedule_service.get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if body.cron_expression and not schedule_service.validate_cron_expression(body.cron_expression):
        raise HTTPException(status_code=422, detail="Invalid cron expression")
    updated = await schedule_service.update_schedule(db, schedule, body)
    return ApiResponse.ok(CronScheduleRead.model_validate(updated))


@router.delete("/{schedule_id}", response_model=ApiResponse[None])
async def delete_schedule(
    schedule_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    schedule = await schedule_service.get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await schedule_service.delete_schedule(db, schedule)
    return ApiResponse.ok(None)
