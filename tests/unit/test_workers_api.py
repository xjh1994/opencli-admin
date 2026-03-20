"""Unit tests for backend/api/v1/workers.py helper functions."""

import pytest
from unittest.mock import MagicMock, patch


# ── _novnc_port ────────────────────────────────────────────────────────────────

def test_novnc_port_first_chrome():
    """chrome (no suffix) maps to base_port + 0."""
    from backend.api.v1.workers import _novnc_port
    assert _novnc_port("http://chrome:9222", 6080) == 6080


def test_novnc_port_second_agent():
    """agent-2 maps to base_port + 1."""
    from backend.api.v1.workers import _novnc_port
    assert _novnc_port("http://agent-2:9222", 6080) == 6081


def test_novnc_port_third_agent():
    """agent-3 maps to base_port + 2."""
    from backend.api.v1.workers import _novnc_port
    assert _novnc_port("http://agent-3:9222", 6080) == 6082


def test_novnc_port_unknown_hostname():
    """Unknown hostname pattern falls back to N=1."""
    from backend.api.v1.workers import _novnc_port
    assert _novnc_port("http://unknown-host:9222", 6080) == 6080


# ── _container_status ─────────────────────────────────────────────────────────

def test_container_status_running():
    """Returns 'running' when Docker container is running."""
    from backend.api.v1.workers import _container_status

    mock_container = MagicMock()
    mock_container.status = "running"
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with patch("docker.from_env", return_value=mock_client):
        status = _container_status("chrome")

    assert status == "running"


def test_container_status_docker_unavailable():
    """Returns 'unknown' when Docker is not available."""
    from backend.api.v1.workers import _container_status

    with patch("docker.from_env", side_effect=Exception("Docker not running")):
        status = _container_status("chrome")

    assert status == "unknown"


def test_container_status_import_error():
    """Returns 'unknown' when docker module not installed."""
    from backend.api.v1.workers import _container_status

    with patch.dict("sys.modules", {"docker": None}):
        status = _container_status("chrome")

    assert status == "unknown"


# ── chrome_pool_status endpoint ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chrome_pool_status(client):
    """chrome-pool endpoint returns pool status dict."""
    from backend.browser_pool import LocalBrowserPool, init_pool

    # Initialize with a real pool so the endpoint works
    init_pool(["http://chrome:9222"], use_redis=False)

    with patch("backend.api.v1.workers._container_status", return_value="running"):
        response = await client.get("/api/v1/workers/chrome-pool")

    assert response.status_code == 200
    data = response.json()["data"]
    assert "endpoints" in data
    assert "total" in data
    assert "available" in data


@pytest.mark.asyncio
async def test_update_endpoint_mode_invalid_encoding(client):
    """PATCH with bad base64 encoding returns 400."""
    response = await client.patch(
        "/api/v1/workers/chrome-pool/!!!invalid!!!/mode",
        json={"mode": "cdp"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_endpoint_mode_not_in_pool(client):
    """PATCH with valid base64 but unknown endpoint returns 404."""
    import base64
    from backend.browser_pool import LocalBrowserPool, init_pool

    init_pool(["http://chrome:9222"], use_redis=False)

    unknown_ep = base64.urlsafe_b64encode(b"http://unknown:9222").decode()
    response = await client.patch(
        f"/api/v1/workers/chrome-pool/{unknown_ep}/mode",
        json={"mode": "cdp"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_endpoint_mode_success(client, db_session):
    """PATCH updates mode for a known endpoint."""
    import base64
    from backend.browser_pool import LocalBrowserPool, init_pool

    init_pool(["http://chrome:9222"], use_redis=False)

    encoded_ep = base64.urlsafe_b64encode(b"http://chrome:9222").decode()
    response = await client.patch(
        f"/api/v1/workers/chrome-pool/{encoded_ep}/mode",
        json={"mode": "cdp"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "cdp"
    assert data["endpoint"] == "http://chrome:9222"
