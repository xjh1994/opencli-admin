"""Integration tests for /api/v1/agents endpoints."""

import pytest


@pytest.fixture
def agent_data():
    return {
        "name": "Test Agent",
        "processor_type": "claude",
        "model": "claude-3-haiku-20240307",
        "prompt_template": "Summarize: {{content}}",
        "processor_config": {},
        "enabled": True,
    }


@pytest.mark.asyncio
async def test_list_agents_empty(client):
    response = await client.get("/api/v1/agents")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_create_agent(client, agent_data):
    response = await client.post("/api/v1/agents", json=agent_data)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Test Agent"
    assert data["processor_type"] == "claude"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_agents_after_create(client, agent_data):
    await client.post("/api/v1/agents", json=agent_data)
    response = await client.get("/api/v1/agents")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_list_agents_filter_enabled(client, agent_data):
    await client.post("/api/v1/agents", json={**agent_data, "enabled": True})
    await client.post("/api/v1/agents", json={**agent_data, "name": "Disabled", "enabled": False})

    response = await client.get("/api/v1/agents?enabled=true")
    assert response.status_code == 200
    agents = response.json()["data"]
    assert all(a["enabled"] for a in agents)


@pytest.mark.asyncio
async def test_get_agent(client, agent_data):
    create_resp = await client.post("/api/v1/agents", json=agent_data)
    agent_id = create_resp.json()["data"]["id"]

    response = await client.get(f"/api/v1/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == agent_id


@pytest.mark.asyncio
async def test_get_agent_not_found(client):
    response = await client.get("/api/v1/agents/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_agent(client, agent_data):
    create_resp = await client.post("/api/v1/agents", json=agent_data)
    agent_id = create_resp.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Updated Agent", "enabled": False},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Updated Agent"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_update_agent_not_found(client):
    response = await client.patch(
        "/api/v1/agents/nonexistent-id",
        json={"name": "New Name"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent(client, agent_data):
    create_resp = await client.post("/api/v1/agents", json=agent_data)
    agent_id = create_resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/api/v1/agents/{agent_id}")
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/agents/{agent_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent_not_found(client):
    response = await client.delete("/api/v1/agents/nonexistent-id")
    assert response.status_code == 404
