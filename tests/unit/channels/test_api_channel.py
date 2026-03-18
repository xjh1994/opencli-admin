"""Unit tests for the API channel."""

import pytest

from backend.channels.api_channel import ApiChannel, _resolve_secrets


def test_resolve_secrets_with_env(monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "secret_value")
    result = _resolve_secrets("Bearer {{secret:MY_TOKEN}}")
    assert result == "Bearer secret_value"


def test_resolve_secrets_missing_env(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    result = _resolve_secrets("{{secret:MISSING_VAR}}")
    assert result == ""


def test_resolve_secrets_no_template():
    result = _resolve_secrets("plain string")
    assert result == "plain string"


@pytest.fixture
def channel():
    return ApiChannel()


@pytest.mark.asyncio
async def test_validate_config_missing_base_url(channel):
    errors = await channel.validate_config({"endpoint": "/test"})
    assert any("base_url" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_missing_endpoint(channel):
    errors = await channel.validate_config({"base_url": "https://api.example.com"})
    assert any("endpoint" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_valid(channel):
    errors = await channel.validate_config({
        "base_url": "https://api.example.com",
        "endpoint": "/data",
    })
    assert errors == []


def test_build_auth_headers_bearer(channel, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "mytoken")
    headers = channel._build_auth_headers({"type": "bearer", "token_env": "API_TOKEN"})
    assert headers == {"Authorization": "Bearer mytoken"}


def test_build_auth_headers_no_auth(channel):
    headers = channel._build_auth_headers({})
    assert headers == {}
