from typing import Optional

from croniter import croniter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schedule import CronSchedule
from backend.schemas.schedule import CronScheduleCreate, CronScheduleUpdate


def validate_cron_expression(expr: str) -> bool:
    return croniter.is_valid(expr)


async def list_schedules(
    session: AsyncSession,
    source_id: Optional[str] = None,
    enabled: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[CronSchedule], int]:
    query = select(CronSchedule).order_by(CronSchedule.created_at.desc())
    count_query = select(func.count()).select_from(CronSchedule)

    if source_id:
        query = query.where(CronSchedule.source_id == source_id)
        count_query = count_query.where(CronSchedule.source_id == source_id)
    if enabled is not None:
        query = query.where(CronSchedule.enabled == enabled)
        count_query = count_query.where(CronSchedule.enabled == enabled)

    total = (await session.execute(count_query)).scalar_one()
    offset = (page - 1) * limit
    result = await session.execute(query.offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_schedule(session: AsyncSession, schedule_id: str) -> Optional[CronSchedule]:
    result = await session.execute(
        select(CronSchedule).where(CronSchedule.id == schedule_id)
    )
    return result.scalar_one_or_none()


async def create_schedule(session: AsyncSession, data: CronScheduleCreate) -> CronSchedule:
    schedule = CronSchedule(**data.model_dump())
    session.add(schedule)
    await session.flush()
    await session.refresh(schedule)
    return schedule


async def update_schedule(
    session: AsyncSession, schedule: CronSchedule, data: CronScheduleUpdate
) -> CronSchedule:
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(schedule, key, value)
    await session.flush()
    await session.refresh(schedule)
    return schedule


async def delete_schedule(session: AsyncSession, schedule: CronSchedule) -> None:
    await session.delete(schedule)
    await session.flush()
