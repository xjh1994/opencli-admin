"""Unit tests for the OpenCLI channel."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.channels.base import ChannelResult
from backend.channels.opencli_channel import (
    OpenCLIChannel,
    _collect_via_agent,
    _parse_csv,
    _parse_json,
    _parse_markdown,
    _parse_table,
    _parse_yaml,
    _run_opencli,
)


# ── Pure parser function tests ─────────────────────────────────────────────────

def test_parse_json_list():
    raw = '[{"id": 1}, {"id": 2}]'
    result = _parse_json(raw)
    assert result == [{"id": 1}, {"id": 2}]


def test_parse_json_single_object_wrapped():
    raw = '{"id": 1, "name": "test"}'
    result = _parse_json(raw)
    assert result == [{"id": 1, "name": "test"}]


def test_parse_json_with_preamble():
    raw = 'Some preamble text\n{"key": "value"}'
    result = _parse_json(raw)
    assert result == [{"key": "value"}]


def test_parse_json_no_json_raises():
    with pytest.raises(ValueError, match="No JSON found"):
        _parse_json("no json here at all")


def test_parse_yaml_list():
    raw = "- id: 1\n  name: alpha\n- id: 2\n  name: beta\n"
    result = _parse_yaml(raw)
    assert len(result) == 2
    assert result[0]["id"] == 1


def test_parse_yaml_dict_wrapped():
    raw = "id: 1\nname: single\n"
    result = _parse_yaml(raw)
    assert result == [{"id": 1, "name": "single"}]


def test_parse_yaml_scalar_wrapped():
    raw = "hello world"
    result = _parse_yaml(raw)
    assert result == [{"content": "hello world"}]


def test_parse_csv_basic():
    raw = "name,age\nAlice,30\nBob,25"
    result = _parse_csv(raw)
    assert len(result) == 2
    assert result[0]["name"] == "Alice"
    assert result[1]["age"] == "25"


def test_parse_csv_empty():
    raw = "name,age\n"
    result = _parse_csv(raw)
    assert result == []


def test_parse_table_with_box_drawing():
    raw = (
        "┌────────┬───────┐\n"
        "│ Name   │ Score │\n"
        "├────────┼───────┤\n"
        "│ Alice  │ 95    │\n"
        "│ Bob    │ 87    │\n"
        "└────────┴───────┘"
    )
    result = _parse_table(raw)
    assert len(result) == 2
    assert result[0]["Name"] == "Alice"
    assert result[1]["Score"] == "87"


def test_parse_table_no_data_lines():
    raw = "no table here"
    result = _parse_table(raw)
    assert result == [{"content": raw}]


def test_parse_table_header_only():
    raw = "│ Name │ Score │\n"
    result = _parse_table(raw)
    # Only a header row, no data rows — falls back to content
    assert result == [{"content": raw}]


def test_parse_markdown_basic():
    raw = (
        "| Name  | Value |\n"
        "| ----- | ----- |\n"
        "| alpha | 1     |\n"
        "| beta  | 2     |\n"
    )
    result = _parse_markdown(raw)
    assert len(result) == 2
    assert result[0]["Name"] == "alpha"
    assert result[1]["Value"] == "2"


def test_parse_markdown_no_table():
    raw = "just plain text"
    result = _parse_markdown(raw)
    assert result == [{"content": raw}]


def test_parse_markdown_only_header():
    raw = "| Name | Value |\n"
    result = _parse_markdown(raw)
    # Only one line — fewer than 2 pipe-starting lines → fallback
    assert result == [{"content": raw}]


# ── _collect_via_agent tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_via_agent_success():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"success": True, "items": [{"x": 1}]})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await _collect_via_agent(
            "http://agent:8000", "example.com", "list", {}, "json", "cdp"
        )

    assert result.success is True
    assert result.items == [{"x": 1}]


@pytest.mark.asyncio
async def test_collect_via_agent_timeout():
    import httpx

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await _collect_via_agent(
            "http://agent:8000", "site", "cmd", {}, "json", "cdp"
        )

    assert result.success is False
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_via_agent_http_error():
    import httpx

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=OSError("connection refused"))
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await _collect_via_agent(
            "http://agent:8000", "site", "cmd", {}, "json", "cdp"
        )

    assert result.success is False
    assert "failed" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_via_agent_error_response():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={"success": False, "error": "command not found"}
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await _collect_via_agent(
            "http://agent:8000", "site", "cmd", {}, "json", "cdp"
        )

    assert result.success is False
    assert "command not found" in result.error


# ── _run_opencli tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_opencli_success():
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b'[{"id":1}]', b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("asyncio.wait_for", return_value=(b'[{"id":1}]', b"")):
            returncode, stdout, stderr = await _run_opencli(
                ["/opt/opencli-cdp/bin/opencli", "example.com", "list"], {}
            )

    assert returncode == 0


@pytest.mark.asyncio
async def test_run_opencli_file_not_found():
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("no such file")):
        with pytest.raises(FileNotFoundError):
            await _run_opencli(["/nonexistent/opencli", "site", "cmd"], {})


@pytest.mark.asyncio
async def test_run_opencli_timeout():
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            with pytest.raises(asyncio.TimeoutError):
                await _run_opencli(["/opt/opencli-cdp/bin/opencli", "site", "cmd"], {})


# ── validate_config tests ──────────────────────────────────────────────────────

@pytest.fixture
def channel():
    return OpenCLIChannel()


@pytest.mark.asyncio
async def test_validate_config_missing_site(channel):
    errors = await channel.validate_config({"command": "list"})
    assert any("site" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_missing_command(channel):
    errors = await channel.validate_config({"site": "example.com"})
    assert any("command" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_valid(channel):
    errors = await channel.validate_config({"site": "example.com", "command": "list"})
    assert errors == []


@pytest.mark.asyncio
async def test_validate_config_missing_both(channel):
    errors = await channel.validate_config({})
    assert len(errors) == 2


# ── health_check tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check_binary_exists(channel):
    with patch("os.path.isfile", return_value=True):
        result = await channel.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_health_check_binary_missing(channel):
    with patch("os.path.isfile", return_value=False):
        result = await channel.health_check()
    assert result is False


# ── collect: agent mode tests ──────────────────────────────────────────────────

def _make_mock_pool(mode="cdp", agent_url="http://agent:8000", agent_protocol="http"):
    pool = MagicMock()
    pool.get_mode = MagicMock(return_value=mode)
    pool.get_agent_url = MagicMock(return_value=agent_url)
    pool.get_agent_protocol = MagicMock(return_value=agent_protocol)
    pool.endpoints = ["http://chrome:9222"]

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value="http://chrome:9222")
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool


def _make_mock_settings(collection_mode="local", task_executor="local"):
    settings = MagicMock()
    settings.collection_mode = collection_mode
    settings.task_executor = task_executor
    return settings


@pytest.mark.asyncio
async def test_collect_agent_mode_http_success(channel):
    """Agent mode with http protocol dispatches to _collect_via_agent."""
    from backend.browser_pool import LocalBrowserPool

    mock_pool = _make_mock_pool(mode="cdp", agent_url="http://agent:8000", agent_protocol="http")
    mock_settings = _make_mock_settings(collection_mode="agent")

    agent_result = ChannelResult.ok([{"item": 1}], site="example.com", command="list")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
        patch("backend.channels.opencli_channel._collect_via_agent", new=AsyncMock(return_value=agent_result)),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list", "format": "json"}, {}
        )

    assert result.success is True
    assert result.items == [{"item": 1}]


@pytest.mark.asyncio
async def test_collect_agent_mode_ws_protocol_not_implemented(channel):
    """Agent mode with ws protocol returns fail (not yet implemented)."""
    from backend.browser_pool import LocalBrowserPool
    from unittest.mock import create_autospec

    # Use create_autospec so isinstance(mock_pool, LocalBrowserPool) is True
    mock_pool = create_autospec(LocalBrowserPool, instance=True)
    mock_pool.get_mode.return_value = "cdp"
    mock_pool.get_agent_url.return_value = "http://agent:8000"
    mock_pool.get_agent_protocol.return_value = "ws"
    mock_pool.endpoints = ["http://chrome:9222"]
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value="http://chrome:9222")
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    mock_settings = _make_mock_settings(collection_mode="agent")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list"}, {}
        )

    assert result.success is False
    assert "WS" in result.error or "ws" in result.error.lower() or "not yet" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_agent_mode_unknown_protocol(channel):
    """Agent mode with unknown protocol returns fail."""
    from backend.browser_pool import LocalBrowserPool
    from unittest.mock import create_autospec

    mock_pool = create_autospec(LocalBrowserPool, instance=True)
    mock_pool.get_mode.return_value = "cdp"
    mock_pool.get_agent_url.return_value = "http://agent:8000"
    mock_pool.get_agent_protocol.return_value = "grpc"
    mock_pool.endpoints = ["http://chrome:9222"]
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value="http://chrome:9222")
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    mock_settings = _make_mock_settings(collection_mode="agent")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list"}, {}
        )

    assert result.success is False
    assert "grpc" in result.error.lower() or "unknown" in result.error.lower()


# ── collect: local (subprocess) mode tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_local_cdp_success(channel):
    """Local CDP mode runs opencli subprocess and parses JSON output."""
    mock_pool = _make_mock_pool(mode="cdp")
    mock_settings = _make_mock_settings(collection_mode="local")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
        patch(
            "backend.channels.opencli_channel._run_opencli",
            new=AsyncMock(return_value=(0, '[{"title": "test"}]', "")),
        ),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list", "format": "json"}, {}
        )

    assert result.success is True
    assert result.items == [{"title": "test"}]


@pytest.mark.asyncio
async def test_collect_local_bridge_mode(channel):
    """Local bridge mode uses bridge binary and sets DAEMON env vars."""
    mock_pool = _make_mock_pool(mode="bridge")
    mock_settings = _make_mock_settings(collection_mode="local")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
        patch(
            "backend.channels.opencli_channel._run_opencli",
            new=AsyncMock(return_value=(0, '[{"r": 1}]', "")),
        ),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list", "format": "json"}, {}
        )

    assert result.success is True


@pytest.mark.asyncio
async def test_collect_local_nonzero_exit_code(channel):
    """Non-zero exit code returns failed ChannelResult."""
    mock_pool = _make_mock_pool(mode="cdp")
    mock_settings = _make_mock_settings(collection_mode="local")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
        patch(
            "backend.channels.opencli_channel._run_opencli",
            new=AsyncMock(return_value=(1, "", "command failed")),
        ),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list"}, {}
        )

    assert result.success is False
    assert "exited with code 1" in result.error


@pytest.mark.asyncio
async def test_collect_local_timeout(channel):
    """asyncio.TimeoutError in subprocess returns failed ChannelResult."""
    mock_pool = _make_mock_pool(mode="cdp")
    mock_settings = _make_mock_settings(collection_mode="local")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
        patch(
            "backend.channels.opencli_channel._run_opencli",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list"}, {}
        )

    assert result.success is False
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_local_binary_not_found(channel):
    """FileNotFoundError in subprocess returns failed ChannelResult."""
    mock_pool = _make_mock_pool(mode="cdp")
    mock_settings = _make_mock_settings(collection_mode="local")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
        patch(
            "backend.channels.opencli_channel._run_opencli",
            new=AsyncMock(side_effect=FileNotFoundError("binary not found")),
        ),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list"}, {}
        )

    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_local_parse_error(channel):
    """Invalid JSON output returns failed ChannelResult."""
    mock_pool = _make_mock_pool(mode="cdp")
    mock_settings = _make_mock_settings(collection_mode="local")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
        patch(
            "backend.channels.opencli_channel._run_opencli",
            new=AsyncMock(return_value=(0, "not valid json at all", "")),
        ),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list", "format": "json"}, {}
        )

    assert result.success is False
    assert "parse" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_subprocess_exception(channel):
    """Generic exception from subprocess returns failed ChannelResult."""
    mock_pool = _make_mock_pool(mode="cdp")
    mock_settings = _make_mock_settings(collection_mode="local")

    with (
        patch("backend.browser_pool.get_pool", return_value=mock_pool),
        patch("backend.config.get_settings", return_value=mock_settings),
        patch(
            "backend.channels.opencli_channel._run_opencli",
            new=AsyncMock(side_effect=OSError("unexpected error")),
        ),
    ):
        result = await channel.collect(
            {"site": "example.com", "command": "list"}, {}
        )

    assert result.success is False
    assert "Failed to run" in result.error
