"""Integration tests for /api/v1/schedules endpoints."""

import pytest


@pytest.fixture
async def created_source(client, sample_source_data):
    resp = await client.post("/api/v1/sources", json=sample_source_data)
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
