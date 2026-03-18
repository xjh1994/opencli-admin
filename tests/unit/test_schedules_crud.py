"""Unit tests for schedule CRUD via service."""

import pytest

from backend.models.source import DataSource
from backend.schemas.schedule import CronScheduleCreate, CronScheduleUpdate
from backend.services import schedule_service


@pytest.fixture
async def source(db_session):
    s = DataSource(
        name="Sched Src",
        channel_type="rss",
        channel_config={"feed_url": "https://ex.com/feed"},
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.asyncio
async def test_create_and_get_schedule(db_session, source):
    data = CronScheduleCreate(
        source_id=source.id,
        name="Every hour",
        cron_expression="0 * * * *",
        timezone="UTC",
    )
    sched = await schedule_service.create_schedule(db_session, data)
    assert sched.id is not None
    assert sched.cron_expression == "0 * * * *"

    fetched = await schedule_service.get_schedule(db_session, sched.id)
    assert fetched is not None
    assert fetched.name == "Every hour"


@pytest.mark.asyncio
async def test_get_schedule_not_found(db_session):
    result = await schedule_service.get_schedule(db_session, "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_list_schedules(db_session, source):
    data1 = CronScheduleCreate(
        source_id=source.id, name="S1", cron_expression="0 * * * *"
    )
    data2 = CronScheduleCreate(
        source_id=source.id, name="S2", cron_expression="*/10 * * * *"
    )
    await schedule_service.create_schedule(db_session, data1)
    await schedule_service.create_schedule(db_session, data2)

    scheds, total = await schedule_service.list_schedules(db_session, source_id=source.id)
    assert total == 2
    assert len(scheds) == 2


@pytest.mark.asyncio
async def test_update_schedule(db_session, source):
    data = CronScheduleCreate(
        source_id=source.id, name="Original", cron_expression="0 * * * *"
    )
    sched = await schedule_service.create_schedule(db_session, data)

    update = CronScheduleUpdate(name="Updated", enabled=False)
    updated = await schedule_service.update_schedule(db_session, sched, update)
    assert updated.name == "Updated"
    assert updated.enabled is False


@pytest.mark.asyncio
async def test_delete_schedule(db_session, source):
    data = CronScheduleCreate(
        source_id=source.id, name="To Delete", cron_expression="0 0 * * *"
    )
    sched = await schedule_service.create_schedule(db_session, data)
    sched_id = sched.id

    await schedule_service.delete_schedule(db_session, sched)
    result = await schedule_service.get_schedule(db_session, sched_id)
    assert result is None
