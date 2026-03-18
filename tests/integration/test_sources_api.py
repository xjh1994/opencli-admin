"""Integration tests for the /api/v1/sources endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_sources_empty(client):
    response = await client.get("/api/v1/sources")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"] == []
    assert data["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_create_source(client, sample_source_data):
    response = await client.post("/api/v1/sources", json=sample_source_data)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == sample_source_data["name"]
    assert data["data"]["channel_type"] == "rss"
    assert "id" in data["data"]


@pytest.mark.asyncio
async def test_get_source(client, sample_source_data):
    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    response = await client.get(f"/api/v1/sources/{source_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == source_id


@pytest.mark.asyncio
async def test_get_source_not_found(client):
    response = await client.get("/api/v1/sources/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_source(client, sample_source_data):
    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/sources/{source_id}",
        json={"name": "Updated Name", "enabled": False},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Updated Name"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_delete_source(client, sample_source_data):
    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/api/v1/sources/{source_id}")
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/sources/{source_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_list_sources_pagination(client, sample_source_data):
    # Create 3 sources
    for i in range(3):
        data = {**sample_source_data, "name": f"Source {i}"}
        await client.post("/api/v1/sources", json=data)

    response = await client.get("/api/v1/sources?page=1&limit=2")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 3
    assert body["meta"]["pages"] == 2


@pytest.mark.asyncio
async def test_test_source_connectivity(client, sample_source_data):
    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    response = await client.post(f"/api/v1/sources/{source_id}/test")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data["data"]
