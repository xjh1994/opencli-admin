"""OpenCLI channel: invokes opencli CLI tool and parses its output."""

import asyncio
import csv
import io
import json
import logging
import os
from typing import Any
from urllib.parse import urlparse

import yaml

from backend.channels.base import AbstractChannel, ChannelResult
from backend.channels.registry import register_channel

logger = logging.getLogger(__name__)

_DAEMON_PORT = 19825
_BRIDGE_BIN = "/opt/opencli-bridge/bin/opencli"
_CDP_BIN = "/opt/opencli-cdp/bin/opencli"


def _parse_json(raw: str) -> list[dict]:
    json_start = next((i for i, ch in enumerate(raw) if ch in ("{", "[")), None)
    if json_start is None:
        raise ValueError(f"No JSON found in output: {raw[:200]!r}")
    data = json.loads(raw[json_start:])
    return data if isinstance(data, list) else [data]


def _parse_yaml(raw: str) -> list[dict]:
    data = yaml.safe_load(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return [{"content": str(data)}]


def _parse_csv(raw: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(raw.strip()))
    return [row for row in reader]


def _parse_table(raw: str) -> list[dict]:
    """Parse cli-table3 Unicode box-drawing table into list of dicts."""
    lines = raw.splitlines()
    data_lines = [l for l in lines if l.strip().startswith("│")]
    if not data_lines:
        return [{"content": raw}]

    def split_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("│").split("│")]

    headers = split_row(data_lines[0])
    rows = []
    for line in data_lines[1:]:
        cells = split_row(line)
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows if rows else [{"content": raw}]


def _parse_markdown(raw: str) -> list[dict]:
    """Parse markdown table into list of dicts."""
    lines = [l.strip() for l in raw.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return [{"content": raw}]

    def split_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    headers = split_row(lines[0])
    rows = []
    for line in lines[2:]:
        cells = split_row(line)
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows if rows else [{"content": raw}]


_PARSERS = {
    "json":  _parse_json,
    "yaml":  _parse_yaml,
    "csv":   _parse_csv,
    "table": _parse_table,
    "md":    _parse_markdown,
}


async def _run_opencli(cmd: list[str], env: dict) -> tuple[int, str, str]:
    """Run opencli subprocess, return (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        return proc.returncode, stdout.decode(), stderr.decode().strip()
    except asyncio.TimeoutError:
        raise
    except FileNotFoundError:
        raise


@register_channel
class OpenCLIChannel(AbstractChannel):
    """Collect data by running the opencli CLI tool."""

    channel_type = "opencli"

    async def collect(
        self, config: dict[str, Any], parameters: dict[str, Any]
    ) -> ChannelResult:
        site = config.get("site", "")
        command = config.get("command", "")
        output_format = config.get("format", "json")

        chrome_endpoint: str | None = parameters.get("chrome_endpoint") or None
        cli_params = {k: v for k, v in parameters.items() if k != "chrome_endpoint"}
        args: dict = {**config.get("args", {}), **cli_params}

        env = os.environ.copy()

        from backend.browser_pool import get_pool
        pool = get_pool()

        async with pool.acquire(endpoint=chrome_endpoint) as cdp_endpoint:
            mode = pool.get_mode(cdp_endpoint)
            opencli_bin = _BRIDGE_BIN if mode == "bridge" else _CDP_BIN

            cmd = [opencli_bin, site, command]
            for key, value in args.items():
                cmd.extend([f"--{key}", str(value)])
            cmd.extend(["-f", output_format])

            if mode == "bridge":
                daemon_host = urlparse(cdp_endpoint).hostname or "chrome-1"
                env.pop("OPENCLI_CDP_ENDPOINT", None)
                env["OPENCLI_DAEMON_HOST"] = daemon_host
                env["OPENCLI_DAEMON_PORT"] = str(_DAEMON_PORT)
                logger.info("opencli bridge | cmd=%s daemon=%s:%s", " ".join(cmd), daemon_host, _DAEMON_PORT)
            else:
                env["OPENCLI_CDP_ENDPOINT"] = cdp_endpoint
                logger.info("opencli cdp | cmd=%s cdp=%s", " ".join(cmd), cdp_endpoint)

            try:
                returncode, stdout_text, stderr_text = await _run_opencli(cmd, env)
            except asyncio.TimeoutError:
                logger.error("opencli timeout | cmd=%s", " ".join(cmd))
                return ChannelResult.fail("opencli command timed out after 120s")
            except FileNotFoundError:
                logger.error("opencli binary not found: %s", opencli_bin)
                return ChannelResult.fail(f"opencli binary not found: {opencli_bin}")
            except Exception as exc:
                logger.exception("opencli subprocess error | %s", exc)
                return ChannelResult.fail(f"Failed to run opencli: {exc}")

            if stderr_text:
                logger.warning("opencli stderr | %s", stderr_text[:500])

            if returncode != 0:
                logger.error("opencli exit=%d | stderr=%s", returncode, stderr_text[:500])
                return ChannelResult.fail(f"opencli exited with code {returncode}: {stderr_text}")

            raw = stdout_text
            logger.debug("opencli stdout | %d chars | preview=%s", len(raw), raw[:200])

        parser = _PARSERS.get(output_format, _PARSERS["json"])
        try:
            items = parser(raw)
        except Exception as exc:
            logger.error("opencli parse error | format=%s error=%s output_preview=%s",
                         output_format, exc, raw[:300])
            return ChannelResult.fail(f"Failed to parse opencli {output_format} output: {exc}")

        logger.info("opencli done | site=%s cmd=%s mode=%s items=%d", site, command, mode, len(items))
        return ChannelResult.ok(items, site=site, command=command)

    async def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not config.get("site"):
            errors.append("'site' is required for opencli channel")
        if not config.get("command"):
            errors.append("'command' is required for opencli channel")
        return errors

    async def health_check(self) -> bool:
        return os.path.isfile(_BRIDGE_BIN) or os.path.isfile(_CDP_BIN)
