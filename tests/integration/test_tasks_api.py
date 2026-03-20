"""Integration tests for /api/v1/tasks endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_list_tasks_empty(client):
    response = await client.get("/api/v1/tasks")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_get_task_not_found(client):
    response = await client.get("/api/v1/tasks/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_task_source_not_found(client):
    response = await client.post(
        "/api/v1/tasks/trigger",
        json={"source_id": "nonexistent", "parameters": {}},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_task_disabled_source(client, sample_source_data):
    disabled_data = {**sample_source_data, "enabled": False}
    create_resp = await client.post("/api/v1/sources", json=disabled_data)
    source_id = create_resp.json()["data"]["id"]

    response = await client.post(
        "/api/v1/tasks/trigger",
        json={"source_id": source_id, "parameters": {}},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_trigger_task_success(client, sample_source_data):
    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    with patch("backend.pipeline.runner.run_collection_pipeline", new=AsyncMock()):
        response = await client.post(
            "/api/v1/tasks/trigger",
            json={"source_id": source_id, "parameters": {"limit": 10}},
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert "task_id" in data


@pytest.mark.asyncio
async def test_list_task_runs(client, sample_source_data):
    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    mock_result = MagicMock()
    mock_result.id = "celery-abc"

    with patch("backend.worker.tasks.run_collection") as mock_task:
        mock_task.apply_async.return_value = mock_result
        trigger_resp = await client.post(
            "/api/v1/tasks/trigger",
            json={"source_id": source_id},
        )

    task_id = trigger_resp.json()["data"]["task_id"]
    response = await client.get(f"/api/v1/tasks/{task_id}/runs")
    assert response.status_code == 200
    # No runs yet (Celery didn't actually execute)
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_tasks_filter_by_source(client, sample_source_data):
    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    mock_result = MagicMock()
    mock_result.id = "celery-abc"
    with patch("backend.worker.tasks.run_collection") as mock_task:
        mock_task.apply_async.return_value = mock_result
        await client.post("/api/v1/tasks/trigger", json={"source_id": source_id})

    response = await client.get(f"/api/v1/tasks?source_id={source_id}")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1
