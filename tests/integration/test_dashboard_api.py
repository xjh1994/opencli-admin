"""Integration tests for the dashboard endpoint."""

import pytest


@pytest.mark.asyncio
async def test_dashboard_stats(client):
    response = await client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "sources" in data
    assert "tasks" in data
    assert "records" in data
    assert "recent_runs" in data
    assert data["sources"]["total"] == 0


@pytest.mark.asyncio
async def test_dashboard_stats_with_source(client, sample_source_data):
    await client.post("/api/v1/sources", json=sample_source_data)
    response = await client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sources"]["total"] == 1
    assert data["sources"]["enabled"] == 1
