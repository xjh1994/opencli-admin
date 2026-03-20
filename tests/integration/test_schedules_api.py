"""Integration tests for /api/v1/schedules endpoints."""

import pytest


@pytest.fixture
async def created_source(client, sample_source_data):
    resp = await client.post("/api/v1/sources", json=sample_source_data)
    return resp.json()["data"]["id"]


@pytest.fixture
async def created_schedule(client, created_source):
    payload = {
        "source_id": created_source,
        "name": "Test Schedule",
        "cron_expression": "0 9 * * *",
    }
    resp = await client.post("/api/v1/schedules", json=payload)
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_schedule(client, created_source):
    payload = {
        "source_id": created_source,
        "name": "Daily at 9am",
        "cron_expression": "0 9 * * *",
        "timezone": "UTC",
    }
    response = await client.post("/api/v1/schedules", json=payload)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["cron_expression"] == "0 9 * * *"
    assert data["source_id"] == created_source


@pytest.mark.asyncio
async def test_create_schedule_invalid_cron(client, created_source):
    payload = {
        "source_id": created_source,
        "name": "Bad cron",
        "cron_expression": "not-a-cron",
    }
    response = await client.post("/api/v1/schedules", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_schedules_empty(client):
    response = await client.get("/api/v1/schedules")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_schedules_after_create(client, created_schedule):
    response = await client.get("/api/v1/schedules")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_get_schedule(client, created_schedule):
    response = await client.get(f"/api/v1/schedules/{created_schedule}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == created_schedule


@pytest.mark.asyncio
async def test_get_schedule_not_found(client):
    response = await client.get("/api/v1/schedules/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_schedule(client, created_schedule):
    response = await client.patch(
        f"/api/v1/schedules/{created_schedule}",
        json={"enabled": False, "name": "Updated Schedule"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["enabled"] is False
    assert data["name"] == "Updated Schedule"


@pytest.mark.asyncio
async def test_update_schedule_invalid_cron(client, created_schedule):
    response = await client.patch(
        f"/api/v1/schedules/{created_schedule}",
        json={"cron_expression": "not-valid-cron"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_schedule_not_found(client):
    response = await client.patch(
        "/api/v1/schedules/nonexistent-id",
        json={"enabled": False},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_schedule(client, created_source):
    payload = {
        "source_id": created_source,
        "name": "To delete",
        "cron_expression": "*/5 * * * *",
    }
    create_resp = await client.post("/api/v1/schedules", json=payload)
    schedule_id = create_resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/api/v1/schedules/{schedule_id}")
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/schedules/{schedule_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_schedule_not_found(client):
    response = await client.delete("/api/v1/schedules/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_schedules_filter_by_source(client, created_source, created_schedule):
    response = await client.get(f"/api/v1/schedules?source_id={created_source}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["source_id"] == created_source


@pytest.mark.asyncio
async def test_list_schedules_filter_enabled(client, created_schedule):
    response = await client.get("/api/v1/schedules?enabled=true")
    assert response.status_code == 200
    schedules = response.json()["data"]
    assert all(s["enabled"] for s in schedules)
