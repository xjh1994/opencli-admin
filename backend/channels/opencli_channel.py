"""OpenCLI channel: invokes opencli CLI tool and parses its output."""

import asyncio
import csv
import io
import json
import logging
import os
import shutil
from typing import Any
from urllib.parse import urlparse

import yaml

from backend.channels.base import AbstractChannel, ChannelResult
from backend.channels.registry import register_channel

logger = logging.getLogger(__name__)

_DAEMON_PORT = 19825
# Binary to invoke. Override with OPENCLI_BIN env var if needed.
_OPENCLI_BIN = os.environ.get("OPENCLI_BIN", "opencli")


def _resolve_bin(mode: str) -> str:  # noqa: ARG001 — mode unused, kept for call-site compat
    return _OPENCLI_BIN


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


async def _collect_via_agent(
    agent_url: str,
    site: str,
    command: str,
    args: dict,
    positional_args: list,
    output_format: str,
    mode: str,
) -> ChannelResult:
    """Dispatch a collection request to a LAN agent server via HTTP POST.

    The cdp_endpoint is intentionally omitted: the agent server uses its own
    locally-configured Chrome (OPENCLI_CDP_ENDPOINT env var on the edge node).
    The pool endpoint is only a logical identifier used by the center for routing.
    """
    import httpx

    url = agent_url.rstrip("/") + "/collect"
    payload = {
        "site": site,
        "command": command,
        "args": args,
        "positional_args": positional_args,
        "format": output_format,
        "mode": mode,
    }
    from backend.config import get_settings
    logger.info("agent dispatch | url=%s site=%s cmd=%s", url, site, command)
    try:
        async with httpx.AsyncClient(timeout=get_settings().agent_http_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.error("agent timeout | url=%s", url)
        return ChannelResult.fail(f"Agent request timed out: {url}")
    except Exception as exc:
        logger.error("agent error | url=%s error=%s", url, exc)
        return ChannelResult.fail(f"Agent request failed: {exc}")

    if not data.get("success"):
        err = data.get("error", "unknown agent error")
        logger.error("agent returned error | %s", err)
        return ChannelResult.fail(f"Agent error: {err}")

    items = data.get("items", [])
    logger.info("agent done | site=%s cmd=%s items=%d", site, command, len(items))
    return ChannelResult.ok(items, site=site, command=command, node_url=agent_url)


async def _collect_via_ws_agent(
    agent_url: str,
    site: str,
    command: str,
    args: dict,
    positional_args: list,
    output_format: str,
    mode: str,
) -> ChannelResult:
    """Dispatch a collect request to a NAT agent via the persistent reverse WS channel."""
    from backend import ws_agent_manager

    logger.info("WS agent dispatch | agent=%s site=%s cmd=%s", agent_url, site, command)
    try:
        result = await ws_agent_manager.dispatch_collect(
            agent_url, site, command, args, positional_args, output_format, mode
        )
    except TimeoutError:
        logger.error("WS agent timeout | agent=%s", agent_url)
        return ChannelResult.fail(f"WS agent timed out: {agent_url!r}")
    except RuntimeError as exc:
        logger.error("WS agent not connected | agent=%s: %s", agent_url, exc)
        return ChannelResult.fail(f"WS agent not connected: {exc}")
    except Exception as exc:
        logger.error("WS agent error | agent=%s: %s", agent_url, exc)
        return ChannelResult.fail(f"WS agent error: {exc}")

    if not result.get("success"):
        err = result.get("error", "unknown agent error")
        logger.error("WS agent returned error | agent=%s: %s", agent_url, err)
        return ChannelResult.fail(f"WS agent error: {err}")

    items = result.get("items", [])
    logger.info("WS agent done | site=%s cmd=%s items=%d", site, command, len(items))
    return ChannelResult.ok(items, site=site, command=command, node_url=agent_url)


async def _cleanup_cdp_tabs(cdp_endpoint: str) -> None:
    """Close any navigated tabs left open in Chrome after a CDP collect.

    Called after every CDP collect (success or failure) so stale tabs cannot
    block the next CDP connection attempt.  Only pages with http/https URLs
    are closed; chrome:// and extension pages are left untouched.
    """
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{cdp_endpoint}/json/list")
            tabs = resp.json()
            for tab in tabs:
                url = tab.get("url", "")
                if tab.get("type") == "page" and url.startswith(("http://", "https://")):
                    tab_id = tab["id"]
                    try:
                        await client.get(f"{cdp_endpoint}/json/close/{tab_id}")
                        logger.info("cleanup: closed tab %s url=%s", tab_id, url[:80])
                    except Exception:
                        pass
    except Exception as exc:
        logger.warning("cleanup: could not close CDP tabs at %s: %s", cdp_endpoint, exc)


async def _run_opencli(cmd: list[str], env: dict) -> tuple[int, str, str]:
    """Run opencli subprocess, return (returncode, stdout, stderr).

    Kills the process on timeout before re-raising so it doesn't linger.
    """
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        from backend.config import get_settings
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=get_settings().opencli_timeout)
        return proc.returncode, stdout.decode(), stderr.decode().strip()
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
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
        positional_args: list[str] = [str(v) for v in config.get("positional_args", [])]

        env = os.environ.copy()

        from backend.browser_pool import get_pool, LocalBrowserPool
        from backend.config import get_settings
        pool = get_pool()
        settings = get_settings()

        # In agent mode, prefer endpoints that have a registered agent_url/protocol.
        # The pool may also contain local chrome endpoints without agent metadata.
        _acquire_endpoint = chrome_endpoint
        if settings.collection_mode == "agent" and not chrome_endpoint and isinstance(pool, LocalBrowserPool):
            agent_eps = [ep for ep in pool.endpoints if pool.get_agent_protocol(ep)]
            if agent_eps:
                _acquire_endpoint = agent_eps[0]
                logger.debug("agent mode: selected endpoint %s (has agent_protocol)", _acquire_endpoint)
            else:
                return ChannelResult.fail("No registered agent nodes available. Please add an agent node first.")

        async with pool.acquire(endpoint=_acquire_endpoint) as cdp_endpoint:
            mode = pool.get_mode(cdp_endpoint)
            # Agent mode: dispatch to remote edge node
            if settings.collection_mode == "agent":
                protocol = pool.get_agent_protocol(cdp_endpoint) if isinstance(pool, LocalBrowserPool) else "http"
                agent_url = pool.get_agent_url(cdp_endpoint) or cdp_endpoint
                if not protocol:
                    return ChannelResult.fail(
                        f"Endpoint {cdp_endpoint} has no registered agent. "
                        "Set COLLECTION_MODE=local or add an agent node."
                    )
                if protocol == "http":
                    return await _collect_via_agent(
                        agent_url, site, command, args, positional_args, output_format, mode
                    )
                elif protocol == "ws":
                    return await _collect_via_ws_agent(
                        agent_url, site, command, args, positional_args, output_format, mode
                    )
                else:
                    logger.error("Unknown agent_protocol %r for endpoint %s", protocol, cdp_endpoint)
                    return ChannelResult.fail(f"Unknown agent_protocol: {protocol!r}")

            opencli_bin = _resolve_bin(mode)

            cmd = [opencli_bin, site, command]
            cmd.extend(positional_args)
            for key, value in args.items():
                cmd.extend([f"--{key}", str(value)])
            cmd.extend(["-f", output_format])

            if mode == "bridge":
                daemon_host = urlparse(cdp_endpoint).hostname or "agent-1"
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
                if mode == "cdp":
                    await _cleanup_cdp_tabs(cdp_endpoint)
                return ChannelResult.fail("opencli command timed out after 120s")
            except FileNotFoundError:
                logger.error("opencli binary not found: %s", opencli_bin)
                return ChannelResult.fail(f"opencli binary not found: {opencli_bin}")
            except Exception as exc:
                logger.exception("opencli subprocess error | %s", exc)
                if mode == "cdp":
                    await _cleanup_cdp_tabs(cdp_endpoint)
                return ChannelResult.fail(f"Failed to run opencli: {exc}")

            if mode == "cdp":
                await _cleanup_cdp_tabs(cdp_endpoint)

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
        return shutil.which(_OPENCLI_BIN) is not None or os.path.isfile(_OPENCLI_BIN)
