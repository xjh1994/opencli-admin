"""API channel: direct REST/GraphQL API calls."""

import os
import re
from typing import Any

import httpx

from backend.channels.base import AbstractChannel, ChannelResult
from backend.channels.registry import register_channel

_SECRET_RE = re.compile(r"\{\{secret:([A-Z_][A-Z0-9_]*)\}\}")


def _resolve_secrets(value: str) -> str:
    """Replace {{secret:ENV_VAR}} placeholders with env var values."""

    def _replace(match: re.Match) -> str:
        env_var = match.group(1)
        return os.environ.get(env_var, "")

    return _SECRET_RE.sub(_replace, value)


def _resolve_dict_secrets(d: dict) -> dict:
    return {k: _resolve_secrets(v) if isinstance(v, str) else v for k, v in d.items()}


@register_channel
class ApiChannel(AbstractChannel):
    """Collect data from REST/GraphQL APIs."""

    channel_type = "api"

    async def collect(
        self, config: dict[str, Any], parameters: dict[str, Any]
    ) -> ChannelResult:
        base_url: str = config.get("base_url", "")
        endpoint: str = config.get("endpoint", "")
        method: str = config.get("method", "GET").upper()
        auth_config: dict = config.get("auth", {})
        query_params: dict = {**config.get("params", {}), **parameters}
        request_body: dict = config.get("body", {})
        extra_headers: dict = _resolve_dict_secrets(config.get("headers", {}))
        timeout: int = config.get("timeout", 30)
        result_path: str = config.get("result_path", "")  # e.g. "data.items"

        url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")

        headers = self._build_auth_headers(auth_config)
        headers.update(extra_headers)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method,
                    url,
                    params=query_params if method == "GET" else None,
                    json=request_body if method != "GET" else None,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.TimeoutException:
            return ChannelResult.fail(f"API request to {url} timed out")
        except httpx.HTTPStatusError as exc:
            return ChannelResult.fail(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return ChannelResult.fail(f"API request failed: {exc}")

        try:
            data = response.json()
        except Exception:
            return ChannelResult.fail("Failed to parse API response as JSON")

        # Navigate to the result path
        if result_path:
            for key in result_path.split("."):
                if isinstance(data, dict):
                    data = data.get(key, [])
                else:
                    break

        items = data if isinstance(data, list) else [data]
        return ChannelResult.ok(items, url=url, status_code=response.status_code)

    def _build_auth_headers(self, auth: dict) -> dict[str, str]:
        auth_type = auth.get("type", "")
        if auth_type == "bearer":
            token_env = auth.get("token_env", "")
            token = os.environ.get(token_env, auth.get("token", ""))
            return {"Authorization": f"Bearer {token}"}
        if auth_type == "basic":
            import base64
            user = _resolve_secrets(auth.get("username", ""))
            pw = _resolve_secrets(auth.get("password", ""))
            encoded = base64.b64encode(f"{user}:{pw}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        if auth_type == "api_key":
            header_name = auth.get("header", "X-API-Key")
            key_env = auth.get("key_env", "")
            key = os.environ.get(key_env, auth.get("key", ""))
            return {header_name: key}
        return {}

    async def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not config.get("base_url"):
            errors.append("'base_url' is required for api channel")
        if not config.get("endpoint"):
            errors.append("'endpoint' is required for api channel")
        return errors
