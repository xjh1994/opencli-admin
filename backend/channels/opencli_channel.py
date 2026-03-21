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

# Cache: (bin, site, command) → frozenset of accepted --option names (excluding builtins)
_help_cache: dict[tuple[str, str, str], frozenset[str]] = {}


async def _get_named_options(bin_path: str, site: str, command: str) -> frozenset[str]:
    """Return the set of --option names accepted by `opencli <site> <command>`.

    Runs `--help` once per (bin, site, command) triple and caches the result.
    Falls back to an empty set on any error so the caller can still try running.
    """
    import re
    key = (bin_path, site, command)
    if key in _help_cache:
        return _help_cache[key]
    try:
        proc = await asyncio.create_subprocess_exec(
            bin_path, site, command, "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        text = stdout.decode(errors="replace")
        # Extract every --flag name; strip built-ins that aren't user-facing options
        names = frozenset(re.findall(r"--([a-zA-Z][a-zA-Z0-9-]*)", text)) - {
            "format", "verbose", "help"
        }
    except Exception as exc:
        logger.debug("could not fetch --help for %s %s: %s", site, command, exc)
        names = frozenset()
    _help_cache[key] = names
    return names


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
    return ChannelResult.ok(items, site=site, command=command, node_url=agent_url, chrome_mode=mode)


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
    return ChannelResult.ok(items, site=site, command=command, node_url=agent_url, chrome_mode=mode)


async def _check_bridge_ready(daemon_host: str, daemon_port: int) -> str | None:
    """Return an error string if the bridge extension is not ready, else None.

    The opencli daemon auto-starts on first use, so a missing daemon is not an
    error here — we only block when the daemon IS running but the extension is
    not yet connected (user needs to install the browser extension).
    """
    import httpx
    status_url = f"http://{daemon_host}:{daemon_port}/status"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(status_url)
            data = resp.json()
    except Exception:
        # Daemon not running yet — opencli will start it automatically; not a blocker
        return None
    if not data.get("extensionConnected"):
        return (
            "opencli Browser Bridge extension is not connected to the daemon. "
            "Install steps: "
            "1) Download the extension from GitHub Releases  "
            "2) Open chrome://extensions/ → Enable Developer Mode  "
            "3) Click 'Load unpacked' → select the extension folder  "
            "Or switch the data source to CDP mode if you have a Chrome CDP endpoint available."
        )
    return None


async def _snapshot_tab_ids(cdp_endpoint: str) -> set[str]:
    """Return the set of tab IDs currently open in Chrome."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{cdp_endpoint}/json/list")
            return {t["id"] for t in resp.json() if "id" in t}
    except Exception:
        return set()


async def _cleanup_cdp_tabs(cdp_endpoint: str, pre_existing_ids: set[str]) -> None:
    """Close only tabs opened by opencli during collection.

    Compares current tab list against pre_existing_ids (snapshotted before the
    collect run) and closes only the new ones.  This prevents closing the user's
    personal Chrome tabs when connecting to a local (non-container) Chrome.

    After closing new tabs, ensures at least one blank page target remains so
    subsequent CDP connections always find an inspectable target.
    """
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{cdp_endpoint}/json/list")
            tabs = resp.json()
            remaining_pages = sum(1 for t in tabs if t.get("type") == "page")
            for tab in tabs:
                tab_id = tab.get("id", "")
                if tab.get("type") == "page" and tab_id not in pre_existing_ids:
                    try:
                        await client.get(f"{cdp_endpoint}/json/close/{tab_id}")
                        logger.info("cleanup: closed new tab %s url=%s", tab_id, tab.get("url", "")[:80])
                        remaining_pages -= 1
                    except Exception:
                        pass
            if remaining_pages == 0:
                try:
                    await client.put(f"{cdp_endpoint}/json/new")
                    logger.info("cleanup: opened blank tab to keep CDP target available")
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
        raw_args: dict = {**config.get("args", {}), **cli_params}
        positional_args: list[str] = [str(v) for v in config.get("positional_args", [])]

        # Resolve which keys in raw_args are valid named --options for this command.
        # Any key not recognised by the binary is passed as a positional arg instead,
        # so configs written for older opencli versions continue to work after upgrades
        # where args like `query` became positional.
        opencli_bin_early = _resolve_bin("cdp")  # mode doesn't affect option names
        named_options = await _get_named_options(opencli_bin_early, site, command)
        args: dict = {}
        extra_positional: list[str] = []
        for k, v in raw_args.items():
            if named_options and k not in named_options:
                logger.debug("arg %r not a named option for %s/%s — passing as positional", k, site, command)
                extra_positional.append(str(v))
            else:
                args[k] = v
        # extra_positional goes first (before explicitly configured positional_args)
        positional_args = extra_positional + positional_args

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
                bridge_err = await _check_bridge_ready(daemon_host, _DAEMON_PORT)
                if bridge_err:
                    logger.error("bridge not ready: %s", bridge_err)
                    return ChannelResult.fail(bridge_err)
            else:
                env["OPENCLI_CDP_ENDPOINT"] = cdp_endpoint
                logger.info("opencli cdp | cmd=%s cdp=%s", " ".join(cmd), cdp_endpoint)

            pre_tab_ids: set[str] = set()
            if mode == "cdp":
                pre_tab_ids = await _snapshot_tab_ids(cdp_endpoint)

            try:
                returncode, stdout_text, stderr_text = await _run_opencli(cmd, env)
            except asyncio.TimeoutError:
                logger.error("opencli timeout | cmd=%s", " ".join(cmd))
                if mode == "cdp":
                    await _cleanup_cdp_tabs(cdp_endpoint, pre_tab_ids)
                return ChannelResult.fail("opencli command timed out after 120s")
            except FileNotFoundError:
                logger.error("opencli binary not found: %s", opencli_bin)
                return ChannelResult.fail(f"opencli binary not found: {opencli_bin}")
            except Exception as exc:
                logger.exception("opencli subprocess error | %s", exc)
                if mode == "cdp":
                    await _cleanup_cdp_tabs(cdp_endpoint, pre_tab_ids)
                return ChannelResult.fail(f"Failed to run opencli: {exc}")

            if mode == "cdp":
                await _cleanup_cdp_tabs(cdp_endpoint, pre_tab_ids)

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
        return ChannelResult.ok(items, site=site, command=command, chrome_mode=mode)

    async def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not config.get("site"):
            errors.append("'site' is required for opencli channel")
        if not config.get("command"):
            errors.append("'command' is required for opencli channel")
        return errors

    async def health_check(self) -> bool:
        if not (shutil.which(_OPENCLI_BIN) or os.path.isfile(_OPENCLI_BIN)):
            return False
        # Binary found; extension connectivity is mode-dependent, not a hard failure here
        return True
