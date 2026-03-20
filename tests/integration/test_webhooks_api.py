"""Integration tests for /api/v1/webhooks endpoints."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_webhook_trigger_source_not_found(client):
    response = await client.post("/api/v1/webhooks/nonexistent-source", json={})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_webhook_trigger_disabled_source(client, sample_source_data):
    disabled_data = {**sample_source_data, "enabled": False}
    create_resp = await client.post("/api/v1/sources", json=disabled_data)
    source_id = create_resp.json()["data"]["id"]

    response = await client.post(f"/api/v1/webhooks/{source_id}", json={})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_trigger_success(client, sample_source_data):
    """Webhook trigger succeeds when HMAC is provided with the default secret."""
    from backend.config import get_settings
    settings = get_settings()
    secret = settings.webhook_secret

    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    payload = json.dumps({"event": "push"}).encode()
    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    with patch("backend.pipeline.runner.run_collection_pipeline", new=AsyncMock()):
        response = await client.post(
            f"/api/v1/webhooks/{source_id}",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Signature-256": signature,
            },
        )

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_webhook_trigger_with_valid_hmac(client, sample_source_data):
    """Webhook with correct HMAC signature passes through."""
    secret = "test-secret"
    source_config = {
        **sample_source_data,
        "channel_config": {
            **sample_source_data["channel_config"],
            "webhook_secret": secret,
        },
    }
    create_resp = await client.post("/api/v1/sources", json=source_config)
    source_id = create_resp.json()["data"]["id"]

    payload = json.dumps({"event": "test"}).encode()
    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    with patch("backend.pipeline.runner.run_collection_pipeline", new=AsyncMock()):
        response = await client.post(
            f"/api/v1/webhooks/{source_id}",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Signature-256": signature,
            },
        )

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_webhook_trigger_with_invalid_hmac(client, sample_source_data):
    """Webhook with wrong HMAC signature is rejected."""
    secret = "test-secret"
    source_config = {
        **sample_source_data,
        "channel_config": {
            **sample_source_data["channel_config"],
            "webhook_secret": secret,
        },
    }
    create_resp = await client.post("/api/v1/sources", json=source_config)
    source_id = create_resp.json()["data"]["id"]

    response = await client.post(
        f"/api/v1/webhooks/{source_id}",
        json={"event": "test"},
        headers={"X-Signature-256": "sha256=invalidsignature"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_trigger_empty_body(client, sample_source_data):
    """Webhook with non-JSON body still creates task with empty parameters."""
    from backend.config import get_settings
    settings = get_settings()
    secret = settings.webhook_secret

    create_resp = await client.post("/api/v1/sources", json=sample_source_data)
    source_id = create_resp.json()["data"]["id"]

    body = b"not json"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    with patch("backend.pipeline.runner.run_collection_pipeline", new=AsyncMock()):
        response = await client.post(
            f"/api/v1/webhooks/{source_id}",
            content=body,
            headers={
                "Content-Type": "text/plain",
                "X-Signature-256": signature,
            },
        )

    assert response.status_code == 202
