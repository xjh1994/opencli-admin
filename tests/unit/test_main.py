"""Unit tests for backend/main.py."""

from unittest.mock import MagicMock, patch

import pytest


# ── _read_chrome_endpoints ─────────────────────────────────────────────────────

def test_read_chrome_endpoints_returns_list(tmp_path):
    """_read_chrome_endpoints parses comma-separated endpoints from .env file."""
    from backend.main import _read_chrome_endpoints

    env_file = tmp_path / ".env"
    env_file.write_text("AGENT_POOL_ENDPOINTS=http://chrome:9222,http://chrome-2:9222\n")

    with patch("dotenv.dotenv_values", return_value={"AGENT_POOL_ENDPOINTS": "http://chrome:9222,http://chrome-2:9222"}):
        result = _read_chrome_endpoints()

    assert result == ["http://chrome:9222", "http://chrome-2:9222"]


def test_read_chrome_endpoints_empty_env():
    """_read_chrome_endpoints returns empty list when AGENT_POOL_ENDPOINTS not set."""
    from backend.main import _read_chrome_endpoints

    with patch("dotenv.dotenv_values", return_value={}):
        result = _read_chrome_endpoints()

    assert result == []


def test_read_chrome_endpoints_strips_whitespace():
    """_read_chrome_endpoints strips whitespace from each endpoint."""
    from backend.main import _read_chrome_endpoints

    with patch("dotenv.dotenv_values", return_value={"AGENT_POOL_ENDPOINTS": " http://chrome:9222 , http://chrome-2:9222 "}):
        result = _read_chrome_endpoints()

    assert result == ["http://chrome:9222", "http://chrome-2:9222"]


def test_read_chrome_endpoints_handles_exception():
    """_read_chrome_endpoints returns empty list if dotenv raises."""
    from backend.main import _read_chrome_endpoints

    with patch("dotenv.dotenv_values", side_effect=ImportError("no dotenv")):
        result = _read_chrome_endpoints()

    assert result == []


def test_read_chrome_endpoints_blank_value():
    """_read_chrome_endpoints returns empty list when value is blank."""
    from backend.main import _read_chrome_endpoints

    with patch("dotenv.dotenv_values", return_value={"AGENT_POOL_ENDPOINTS": "  "}):
        result = _read_chrome_endpoints()

    assert result == []


# ── create_app ────────────────────────────────────────────────────────────────

def test_create_app_returns_fastapi_app():
    """create_app returns a FastAPI application instance."""
    from fastapi import FastAPI
    from backend.main import create_app

    created = create_app()
    assert isinstance(created, FastAPI)


def test_app_has_health_endpoint(client):
    """GET /health returns ok status."""
    import asyncio

    async def _check():
        from httpx import ASGITransport, AsyncClient
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")
        return response

    response = asyncio.get_event_loop().run_until_complete(_check())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_app_has_openapi_docs():
    """GET /openapi.json returns OpenAPI schema."""
    import asyncio
    from httpx import ASGITransport, AsyncClient
    from backend.main import app

    async def _check():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            return await ac.get("/openapi.json")

    response = asyncio.get_event_loop().run_until_complete(_check())
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "paths" in schema
