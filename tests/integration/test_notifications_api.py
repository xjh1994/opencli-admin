"""Integration tests for /api/v1/notifications endpoints."""

import pytest


@pytest.fixture
def rule_data():
    return {
        "name": "Test Webhook Rule",
        "trigger_event": "on_new_record",
        "notifier_type": "webhook",
        "notifier_config": {"url": "https://hooks.example.com/test"},
        "enabled": True,
    }


@pytest.mark.asyncio
async def test_list_rules_empty(client):
    response = await client.get("/api/v1/notifications/rules")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_create_rule(client, rule_data):
    response = await client.post("/api/v1/notifications/rules", json=rule_data)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Test Webhook Rule"
    assert data["notifier_type"] == "webhook"


@pytest.mark.asyncio
async def test_get_rule(client, rule_data):
    create_resp = await client.post("/api/v1/notifications/rules", json=rule_data)
    rule_id = create_resp.json()["data"]["id"]

    response = await client.get(f"/api/v1/notifications/rules/{rule_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == rule_id


@pytest.mark.asyncio
async def test_get_rule_not_found(client):
    response = await client.get("/api/v1/notifications/rules/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_rule(client, rule_data):
    create_resp = await client.post("/api/v1/notifications/rules", json=rule_data)
    rule_id = create_resp.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/notifications/rules/{rule_id}",
        json={"name": "Updated Rule", "enabled": False},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Updated Rule"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_delete_rule(client, rule_data):
    create_resp = await client.post("/api/v1/notifications/rules", json=rule_data)
    rule_id = create_resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/api/v1/notifications/rules/{rule_id}")
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/notifications/rules/{rule_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_list_logs_empty(client):
    response = await client.get("/api/v1/notifications/logs")
    assert response.status_code == 200
    assert response.json()["data"] == []
