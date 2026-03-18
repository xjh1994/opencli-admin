from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.record import CollectedRecord


async def list_records(
    session: AsyncSession,
    source_id: Optional[str] = None,
    task_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[CollectedRecord], int]:
    query = select(CollectedRecord).order_by(CollectedRecord.created_at.desc())
    count_query = select(func.count()).select_from(CollectedRecord)

    filters = []
    if source_id:
        filters.append(CollectedRecord.source_id == source_id)
    if task_id:
        filters.append(CollectedRecord.task_id == task_id)
    if status:
        filters.append(CollectedRecord.status == status)

    if filters:
        for f in filters:
            query = query.where(f)
            count_query = count_query.where(f)

    total = (await session.execute(count_query)).scalar_one()
    offset = (page - 1) * limit
    result = await session.execute(query.offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_record(
    session: AsyncSession, record_id: str
) -> Optional[CollectedRecord]:
    result = await session.execute(
        select(CollectedRecord).where(CollectedRecord.id == record_id)
    )
    return result.scalar_one_or_none()
