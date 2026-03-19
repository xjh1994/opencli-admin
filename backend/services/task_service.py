from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.task import CollectionTask, TaskRun
from backend.schemas.task import TaskTriggerRequest


async def create_task(
    session: AsyncSession,
    source_id: str,
    trigger_type: str,
    parameters: dict,
    priority: int = 5,
    agent_id: Optional[str] = None,
) -> CollectionTask:
    task = CollectionTask(
        source_id=source_id,
        agent_id=agent_id,
        trigger_type=trigger_type,
        parameters=parameters,
        priority=priority,
        status="pending",
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def get_task(session: AsyncSession, task_id: str) -> Optional[CollectionTask]:
    result = await session.execute(
        select(CollectionTask).where(CollectionTask.id == task_id)
    )
    return result.scalar_one_or_none()


async def list_tasks(
    session: AsyncSession,
    source_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[CollectionTask], int]:
    query = select(CollectionTask).order_by(CollectionTask.created_at.desc())
    count_query = select(func.count()).select_from(CollectionTask)

    if source_id:
        query = query.where(CollectionTask.source_id == source_id)
        count_query = count_query.where(CollectionTask.source_id == source_id)
    if status:
        query = query.where(CollectionTask.status == status)
        count_query = count_query.where(CollectionTask.status == status)

    total = (await session.execute(count_query)).scalar_one()
    offset = (page - 1) * limit
    result = await session.execute(query.offset(offset).limit(limit))
    return result.scalars().all(), total


async def list_task_runs(
    session: AsyncSession,
    task_id: str,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[TaskRun], int]:
    count_query = select(func.count()).select_from(TaskRun).where(TaskRun.task_id == task_id)
    total = (await session.execute(count_query)).scalar_one()

    result = await session.execute(
        select(TaskRun)
        .where(TaskRun.task_id == task_id)
        .order_by(TaskRun.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return result.scalars().all(), total
