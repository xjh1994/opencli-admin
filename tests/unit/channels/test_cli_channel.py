"""Unit tests for the CLI channel."""

import pytest

from backend.channels.cli_channel import CLIChannel, _render_template


def test_render_template_basic():
    assert _render_template("hello {{name}}", {"name": "world"}) == "hello world"


def test_render_template_missing_key():
    assert _render_template("{{missing}}", {}) == "{{missing}}"


def test_render_template_multiple_keys():
    result = _render_template("{{a}} and {{b}}", {"a": "foo", "b": "bar"})
    assert result == "foo and bar"


@pytest.fixture
def channel():
    return CLIChannel()


@pytest.mark.asyncio
async def test_validate_config_missing_binary(channel):
    errors = await channel.validate_config({"command": ["search"]})
    assert any("binary" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_missing_command(channel):
    errors = await channel.validate_config({"binary": "mycli"})
    assert any("command" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_valid(channel):
    errors = await channel.validate_config({
        "binary": "mycli",
        "command": ["search", "--keyword", "test"],
    })
    assert errors == []


@pytest.mark.asyncio
async def test_collect_binary_not_found(channel):
    result = await channel.collect(
        {"binary": "nonexistent_binary_xyz", "command": ["run"]},
        {},
    )
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_json_output(channel):
    # Use `echo` to simulate JSON output
    import json
    data = [{"title": "Test"}, {"title": "Other"}]
    json_str = json.dumps(data)

    result = await channel.collect(
        {"binary": "sh", "command": ["-c", f"echo '{json_str}'"], "output_format": "json"},
        {},
    )
    assert result.success is True
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_collect_text_output(channel):
    result = await channel.collect(
        {"binary": "sh", "command": ["-c", "printf 'line1\\nline2\\nline3'"], "output_format": "text"},
        {},
    )
    assert result.success is True
    assert len(result.items) == 3
