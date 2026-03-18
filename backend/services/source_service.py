from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.channels.registry import get_channel
from backend.models.source import DataSource
from backend.schemas.source import DataSourceCreate, DataSourceUpdate


async def list_sources(
    session: AsyncSession,
    enabled: Optional[bool] = None,
    channel_type: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[DataSource], int]:
    query = select(DataSource).order_by(DataSource.created_at.desc())
    count_query = select(func.count()).select_from(DataSource)

    if enabled is not None:
        query = query.where(DataSource.enabled == enabled)
        count_query = count_query.where(DataSource.enabled == enabled)
    if channel_type:
        query = query.where(DataSource.channel_type == channel_type)
        count_query = count_query.where(DataSource.channel_type == channel_type)

    total = (await session.execute(count_query)).scalar_one()
    offset = (page - 1) * limit
    result = await session.execute(query.offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_source(session: AsyncSession, source_id: str) -> Optional[DataSource]:
    result = await session.execute(
        select(DataSource).where(DataSource.id == source_id)
    )
    return result.scalar_one_or_none()


async def create_source(session: AsyncSession, data: DataSourceCreate) -> DataSource:
    source = DataSource(**data.model_dump())
    session.add(source)
    await session.flush()
    await session.refresh(source)
    return source


async def update_source(
    session: AsyncSession, source: DataSource, data: DataSourceUpdate
) -> DataSource:
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(source, key, value)
    await session.flush()
    await session.refresh(source)
    return source


async def delete_source(session: AsyncSession, source: DataSource) -> None:
    await session.delete(source)
    await session.flush()


async def validate_source_config(source: DataSource) -> list[str]:
    try:
        channel = get_channel(source.channel_type)
        return await channel.validate_config(source.channel_config)
    except ValueError as exc:
        return [str(exc)]


async def test_source_connectivity(source: DataSource) -> tuple[bool, list[str]]:
    errors = await validate_source_config(source)
    if errors:
        return False, errors
    try:
        channel = get_channel(source.channel_type)
        ok = await channel.health_check()
        return ok, []
    except Exception as exc:
        return False, [str(exc)]
