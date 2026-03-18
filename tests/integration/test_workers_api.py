"""Integration tests for /api/v1/workers endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_workers_empty(client):
    response = await client.get("/api/v1/workers")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_celery_stats(client):
    response = await client.get("/api/v1/workers/celery-stats")
    assert response.status_code == 200
    data = response.json()["data"]
    # Returns error dict if Celery not running
    assert "stats" in data or "error" in data
