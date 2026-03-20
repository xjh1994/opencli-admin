"""Integration tests for /api/v1/records endpoints."""

import pytest

from backend.models.record import CollectedRecord
from backend.models.source import DataSource
from backend.models.task import CollectionTask


async def _create_record(db_session, source_id, task_id, content_hash="hash123"):
    """Helper to create a CollectedRecord in the DB directly."""
    record = CollectedRecord(
        task_id=task_id,
        source_id=source_id,
        raw_data={"title": "Test"},
        normalized_data={"title": "Test", "url": "https://ex.com"},
        content_hash=content_hash,
        status="normalized",
    )
    db_session.add(record)
    await db_session.flush()
    return record


@pytest.fixture
async def source_and_task(db_session):
    """Create a source and task for FK constraints."""
    source = DataSource(
        name="Test Source",
        channel_type="rss",
        channel_config={"feed_url": "https://example.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    return source.id, task.id


@pytest.mark.asyncio
async def test_list_records_empty(client):
    response = await client.get("/api/v1/records")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"] == []
    assert data["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_get_record_not_found(client):
    response = await client.get("/api/v1/records/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_records_with_filters(client):
    response = await client.get("/api/v1/records?source_id=abc&status=raw")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_get_record_success(client, db_session, source_and_task):
    source_id, task_id = source_and_task
    record = await _create_record(db_session, source_id, task_id)

    response = await client.get(f"/api/v1/records/{record.id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == record.id


@pytest.mark.asyncio
async def test_delete_record_success(client, db_session, source_and_task):
    source_id, task_id = source_and_task
    record = await _create_record(db_session, source_id, task_id)

    response = await client.delete(f"/api/v1/records/{record.id}")
    assert response.status_code == 200

    get_resp = await client.get(f"/api/v1/records/{record.id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_record_not_found(client):
    response = await client.delete("/api/v1/records/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_batch_delete_records(client, db_session, source_and_task):
    source_id, task_id = source_and_task
    rec1 = await _create_record(db_session, source_id, task_id, "hash-batch-1")
    rec2 = await _create_record(db_session, source_id, task_id, "hash-batch-2")

    response = await client.post(
        "/api/v1/records/batch-delete",
        json={"ids": [rec1.id, rec2.id]},
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] == 2


@pytest.mark.asyncio
async def test_batch_delete_empty_ids(client):
    response = await client.post(
        "/api/v1/records/batch-delete",
        json={"ids": []},
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] == 0


@pytest.mark.asyncio
async def test_clear_all_records(client, db_session, source_and_task):
    source_id, task_id = source_and_task
    await _create_record(db_session, source_id, task_id, "hash-clear-1")
    await _create_record(db_session, source_id, task_id, "hash-clear-2")

    response = await client.delete(f"/api/v1/records?source_id={source_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["deleted"] >= 2


@pytest.mark.asyncio
async def test_list_records_pagination(client, db_session, source_and_task):
    source_id, task_id = source_and_task
    for i in range(3):
        await _create_record(db_session, source_id, task_id, f"hash-pag-{i}")

    response = await client.get("/api/v1/records?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) <= 2
    assert data["meta"]["total"] >= 3
