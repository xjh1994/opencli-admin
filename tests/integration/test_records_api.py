"""Integration tests for /api/v1/records endpoints."""

import pytest


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
