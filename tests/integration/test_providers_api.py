"""Integration tests for /api/v1/providers endpoints."""

import pytest


@pytest.fixture
def provider_data():
    return {
        "name": "Test Provider",
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test-key",
        "default_model": "gpt-4o-mini",
        "enabled": True,
    }


@pytest.mark.asyncio
async def test_list_providers_empty(client):
    response = await client.get("/api/v1/providers")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_create_provider(client, provider_data):
    response = await client.post("/api/v1/providers", json=provider_data)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Test Provider"
    assert data["provider_type"] == "openai"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_providers_after_create(client, provider_data):
    await client.post("/api/v1/providers", json=provider_data)
    response = await client.get("/api/v1/providers")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_update_provider(client, provider_data):
    create_resp = await client.post("/api/v1/providers", json=provider_data)
    provider_id = create_resp.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/providers/{provider_id}",
        json={"name": "Updated Provider", "enabled": False},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Updated Provider"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_update_provider_not_found(client):
    response = await client.patch(
        "/api/v1/providers/nonexistent-id",
        json={"name": "New Name"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_provider(client, provider_data):
    create_resp = await client.post("/api/v1/providers", json=provider_data)
    provider_id = create_resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/api/v1/providers/{provider_id}")
    assert delete_resp.status_code == 200

    list_resp = await client.get("/api/v1/providers")
    assert list_resp.json()["data"] == []


@pytest.mark.asyncio
async def test_delete_provider_not_found(client):
    response = await client.delete("/api/v1/providers/nonexistent-id")
    assert response.status_code == 404
