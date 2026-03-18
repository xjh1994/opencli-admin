"""Unit tests for service layer functions."""

import pytest

from backend.models.source import DataSource
from backend.models.task import CollectionTask
from backend.schemas.source import DataSourceCreate, DataSourceUpdate
from backend.schemas.task import TaskTriggerRequest
from backend.services import record_service, source_service, task_service


@pytest.mark.asyncio
async def test_create_and_get_source(db_session):
    data = DataSourceCreate(
        name="My Source",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed"},
        tags=["news"],
    )
    source = await source_service.create_source(db_session, data)
    assert source.id is not None
    assert source.name == "My Source"

    fetched = await source_service.get_source(db_session, source.id)
    assert fetched is not None
    assert fetched.name == "My Source"


@pytest.mark.asyncio
async def test_get_source_not_found(db_session):
    result = await source_service.get_source(db_session, "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_list_sources_empty(db_session):
    sources, total = await source_service.list_sources(db_session)
    assert sources == []
    assert total == 0


@pytest.mark.asyncio
async def test_update_source(db_session):
    data = DataSourceCreate(
        name="Original",
        channel_type="api",
        channel_config={"base_url": "https://api.com", "endpoint": "/data"},
    )
    source = await source_service.create_source(db_session, data)

    update = DataSourceUpdate(name="Updated", enabled=False)
    updated = await source_service.update_source(db_session, source, update)
    assert updated.name == "Updated"
    assert updated.enabled is False


@pytest.mark.asyncio
async def test_delete_source(db_session):
    data = DataSourceCreate(
        name="To Delete",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com"},
    )
    source = await source_service.create_source(db_session, data)
    source_id = source.id

    await source_service.delete_source(db_session, source)

    result = await source_service.get_source(db_session, source_id)
    assert result is None


@pytest.mark.asyncio
async def test_create_task(db_session):
    # Create source first
    source = DataSource(
        name="Src",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed"},
    )
    db_session.add(source)
    await db_session.flush()

    task = await task_service.create_task(
        db_session,
        source_id=source.id,
        trigger_type="manual",
        parameters={"limit": 10},
        priority=7,
    )
    assert task.id is not None
    assert task.status == "pending"
    assert task.priority == 7


@pytest.mark.asyncio
async def test_list_tasks(db_session):
    source = DataSource(
        name="Src2",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed"},
    )
    db_session.add(source)
    await db_session.flush()

    await task_service.create_task(db_session, source.id, "manual", {})
    await task_service.create_task(db_session, source.id, "webhook", {})

    tasks, total = await task_service.list_tasks(db_session, source_id=source.id)
    assert total == 2
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_list_records_empty(db_session):
    records, total = await record_service.list_records(db_session)
    assert records == []
    assert total == 0


@pytest.mark.asyncio
async def test_get_record_not_found(db_session):
    result = await record_service.get_record(db_session, "nonexistent")
    assert result is None
