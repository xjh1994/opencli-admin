"""Integration tests: opencli channel with positional_args through real API routes.

Strategy:
  - Create a source via POST /api/v1/sources (real DB, real FastAPI app)
  - Read the source back via GET /api/v1/sources/{id} to get stored config
  - Instantiate OpenCLIChannel and call collect() directly, patching the subprocess
  - Assert the command line contains positional args in the correct position

Background tasks bypass FastAPI's DB dependency injection (they use the
module-level AsyncSessionLocal), so we avoid the trigger→poll approach.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_subprocess_mock(stdout: str = '[{"title":"result1"}]'):
    proc = MagicMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(stdout.encode(), b""))
    proc.kill = MagicMock()
    return proc


def _pool_mock(mode: str = "bridge"):
    """Return a mock browser pool in local mode."""
    pool = MagicMock()
    pool.endpoints = ["http://localhost:19222"]
    pool.get_mode.return_value = mode
    pool.get_agent_protocol.return_value = None
    pool.get_agent_url.return_value = None

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value="http://localhost:19222")
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool


def _settings_mock(collection_mode: str = "local"):
    s = MagicMock()
    s.collection_mode = collection_mode
    s.opencli_timeout = 30
    s.agent_http_timeout = 30
    s.agent_ws_timeout = 30
    return s


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def opencli_source_payload():
    return {
        "name": "Bilibili Search – AI agent",
        "channel_type": "opencli",
        "channel_config": {
            "site": "bilibili",
            "command": "search",
            "positional_args": ["AI agent"],
            "args": {"type": "video", "limit": "5"},
            "format": "json",
        },
        "enabled": True,
    }


@pytest.fixture
def opencli_source_no_positional():
    return {
        "name": "Zhihu Hot",
        "channel_type": "opencli",
        "channel_config": {
            "site": "zhihu",
            "command": "hot",
            "args": {"limit": "10"},
            "format": "json",
        },
        "enabled": True,
    }


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_opencli_source_stores_positional_args(client, opencli_source_payload):
    """API correctly persists positional_args in channel_config."""
    resp = await client.post("/api/v1/sources", json=opencli_source_payload)
    assert resp.status_code == 201
    cfg = resp.json()["data"]["channel_config"]
    assert cfg["positional_args"] == ["AI agent"]
    assert cfg["args"] == {"type": "video", "limit": "5"}


@pytest.mark.asyncio
async def test_source_roundtrip_positional_args(client, opencli_source_payload):
    """positional_args survive a create → GET roundtrip unchanged."""
    create_resp = await client.post("/api/v1/sources", json=opencli_source_payload)
    source_id = create_resp.json()["data"]["id"]

    get_resp = await client.get(f"/api/v1/sources/{source_id}")
    assert get_resp.status_code == 200
    cfg = get_resp.json()["data"]["channel_config"]
    assert cfg["positional_args"] == ["AI agent"]


@pytest.mark.asyncio
async def test_collect_builds_cmd_with_positional_args_before_named_options(
    client, opencli_source_payload
):
    """Channel builds: [binary, site, command, <positionals>, --options, -f fmt]"""
    from backend.channels.opencli_channel import OpenCLIChannel

    create_resp = await client.post("/api/v1/sources", json=opencli_source_payload)
    cfg = create_resp.json()["data"]["channel_config"]

    captured: list[list] = []

    async def fake_subprocess(*cmd, **kwargs):
        captured.append(list(cmd))
        return _make_subprocess_mock()

    with (
        patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess),
        patch("backend.browser_pool.get_pool", return_value=_pool_mock("bridge")),
        patch("backend.config.get_settings", return_value=_settings_mock("local")),
    ):
        channel = OpenCLIChannel()
        result = await channel.collect(cfg, {})

    assert result.success, f"collect failed: {result.error}"
    assert len(captured) == 1
    cmd = captured[0]

    # Expected: [..., "bilibili", "search", "AI agent", "--type", "video", "--limit", "5", "-f", "json"]
    site_idx = cmd.index("bilibili")
    assert cmd[site_idx + 1] == "search"
    assert cmd[site_idx + 2] == "AI agent", (
        f"positional arg must immediately follow command, got: {cmd[site_idx+2:]}"
    )
    assert "--type" in cmd
    assert "--limit" in cmd
    assert cmd[-2:] == ["-f", "json"]


@pytest.mark.asyncio
async def test_collect_without_positional_args_backward_compat(
    client, opencli_source_no_positional
):
    """Sources without positional_args: named options come right after command."""
    from backend.channels.opencli_channel import OpenCLIChannel

    create_resp = await client.post("/api/v1/sources", json=opencli_source_no_positional)
    cfg = create_resp.json()["data"]["channel_config"]

    captured: list[list] = []

    async def fake_subprocess(*cmd, **kwargs):
        captured.append(list(cmd))
        return _make_subprocess_mock()

    with (
        patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess),
        patch("backend.browser_pool.get_pool", return_value=_pool_mock("cdp")),
        patch("backend.config.get_settings", return_value=_settings_mock("local")),
    ):
        channel = OpenCLIChannel()
        result = await channel.collect(cfg, {})

    assert result.success, f"collect failed: {result.error}"
    assert len(captured) == 1
    cmd = captured[0]

    site_idx = cmd.index("zhihu")
    assert cmd[site_idx + 1] == "hot"
    # No positional args — first thing after "hot" is a named option
    assert cmd[site_idx + 2].startswith("--"), (
        f"expected named option after command, got: {cmd[site_idx+2:]}"
    )
    assert "--limit" in cmd
    assert "10" in cmd


@pytest.mark.asyncio
async def test_collect_agent_mode_passes_positional_args_to_dispatch(
    client, opencli_source_payload
):
    """In HTTP agent mode, positional_args is forwarded to _collect_via_agent."""
    from backend.channels.opencli_channel import OpenCLIChannel
    from backend.browser_pool import LocalBrowserPool

    create_resp = await client.post("/api/v1/sources", json=opencli_source_payload)
    cfg = create_resp.json()["data"]["channel_config"]

    captured: list[dict] = []

    async def fake_collect_via_agent(agent_url, site, command, args, positional_args, fmt, mode):
        captured.append({"positional_args": positional_args, "args": args})
        from backend.channels.base import ChannelResult
        return ChannelResult.ok([{"title": "ok"}], site=site, command=command)

    agent_pool = MagicMock(spec=LocalBrowserPool)
    agent_pool.endpoints = ["http://agent:19823"]
    agent_pool.get_agent_protocol.return_value = "http"
    agent_pool.get_agent_url.return_value = "http://agent:19823"
    agent_pool.get_mode.return_value = "bridge"
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value="http://agent:19823")
    ctx.__aexit__ = AsyncMock(return_value=False)
    agent_pool.acquire.return_value = ctx

    with (
        patch(
            "backend.channels.opencli_channel._collect_via_agent",
            side_effect=fake_collect_via_agent,
        ),
        patch("backend.browser_pool.get_pool", return_value=agent_pool),
        patch("backend.config.get_settings", return_value=_settings_mock("agent")),
    ):
        channel = OpenCLIChannel()
        result = await channel.collect(cfg, {})

    assert result.success, f"collect failed: {result.error}"
    assert len(captured) == 1
    assert captured[0]["positional_args"] == ["AI agent"]
    assert captured[0]["args"].get("type") == "video"
