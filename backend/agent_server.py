"""OpenCLI Agent Server — runs on LAN/NAT edge nodes.

Accepts HTTP POST /collect requests from the center API, executes opencli
locally (pointing at the node's own Chrome instance), and returns results.

Registration modes (AGENT_REGISTER):
  http  — LAN mode: agent POSTs its URL to center; center calls back via HTTP.
           Requires the agent to be reachable from the center.
  ws    — NAT/reverse-channel mode: agent initiates a persistent WebSocket to
           the center's /api/v1/nodes/ws endpoint.  The center pushes
           collect tasks down the WS connection; agent returns results in-band.
           Use this when the center cannot reach the agent (NAT, firewall, etc.).
  off   — Disable auto-registration entirely.

Usage on the edge node:
    pip install fastapi uvicorn httpx pyyaml websockets
    python -m backend.agent_server
    # or standalone:
    uvicorn backend.agent_server:app --host 0.0.0.0 --port 19823

Environment variables:
    AGENT_PORT              HTTP port to listen on (default: 19823)
    AGENT_ADVERTISE_URL     Canonical URL the center uses to identify this agent
                            (default: auto-detected from outbound IP)
    AGENT_MODE              Collection mode reported to center: bridge | cdp (default: bridge)
    AGENT_LABEL             Human-readable label for this agent (default: hostname)
    AGENT_REGISTER          Registration mode: http | ws | off (default: http)
    CENTRAL_API_URL         Center API base URL for self-registration
                            e.g. http://192.168.1.1:8031
                            Leave empty to skip auto-registration.
    HTTP_PROXY              HTTP proxy for outbound requests (agent → center)
    HTTPS_PROXY             HTTPS proxy for outbound requests (agent → center)
    OPENCLI_BRIDGE_BIN      Path to opencli 1.0 binary (default: /opt/opencli-bridge/bin/opencli)
    OPENCLI_CDP_BIN         Path to opencli 0.9 binary (default: /opt/opencli-cdp/bin/opencli)
    OPENCLI_CDP_ENDPOINT    Default Chrome CDP endpoint (default: http://localhost:19222)
    OPENCLI_DAEMON_PORT     Bridge daemon port (default: 19825)
    OPENCLI_TIMEOUT         opencli subprocess timeout in seconds (default: 120)
"""

import asyncio
import csv
import io
import json
import logging
import os
import socket
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import yaml
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("agent_server")

_BRIDGE_BIN = os.environ.get("OPENCLI_BRIDGE_BIN", "/opt/opencli-bridge/bin/opencli")
_CDP_BIN = os.environ.get("OPENCLI_CDP_BIN", "/opt/opencli-cdp/bin/opencli")
_DEFAULT_CDP = os.environ.get("OPENCLI_CDP_ENDPOINT", "http://localhost:19222")
_DAEMON_PORT = int(os.environ.get("OPENCLI_DAEMON_PORT", "19825"))
_AGENT_PORT = int(os.environ.get("AGENT_PORT", "19823"))
_CENTRAL_API_URL = os.environ.get("CENTRAL_API_URL", "").rstrip("/")
_AGENT_ADVERTISE_URL = os.environ.get("AGENT_ADVERTISE_URL", "")
_AGENT_MODE = os.environ.get("AGENT_MODE", "bridge")
_AGENT_LABEL = os.environ.get("AGENT_LABEL", socket.gethostname())
# Registration mode:
#   http — LAN mode: agent POSTs its URL to center, center calls back via HTTP (default)
#   ws   — NAT/reverse-channel mode: agent opens WS to center, registration via WS handshake (Phase 2)
#   off  — disable auto-registration entirely
_AGENT_REGISTER = os.environ.get("AGENT_REGISTER", "http").lower()
# opencli subprocess execution timeout in seconds
_OPENCLI_TIMEOUT = int(os.environ.get("OPENCLI_TIMEOUT", "120"))
# Outbound proxy for agent → center communication (optional)
_HTTP_PROXY = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""
_HTTPS_PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""


def _detect_advertise_url() -> str:
    """Auto-detect the IP this node would use to reach the center, then build agent URL."""
    if _AGENT_ADVERTISE_URL:
        return _AGENT_ADVERTISE_URL.rstrip("/")
    try:
        # Use center host to detect outbound IP
        target = urlparse(_CENTRAL_API_URL).hostname or "8.8.8.8"
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target, 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = socket.gethostbyname(socket.gethostname())
    return f"http://{ip}:{_AGENT_PORT}"


def _build_proxies() -> dict:
    """Build httpx proxy dict from environment variables."""
    proxies: dict = {}
    if _HTTPS_PROXY:
        proxies["https://"] = _HTTPS_PROXY
    if _HTTP_PROXY:
        proxies["http://"] = _HTTP_PROXY
    return proxies


async def _register_with_center(advertise_url: str) -> None:
    """POST agent registration to the center API. Retries up to 5 times."""
    import httpx

    url = f"{_CENTRAL_API_URL}/api/v1/nodes/register"
    payload = {"agent_url": advertise_url, "mode": _AGENT_MODE, "label": _AGENT_LABEL,
               "agent_protocol": "http"}
    proxies = _build_proxies()

    for attempt in range(1, 6):
        try:
            # httpx >= 0.28 removed 'proxies'; use 'proxy' (single URL) or mounts
            client_kwargs: dict = {"timeout": 10}
            if proxies:
                proxy_url = proxies.get("https://") or proxies.get("http://")
                try:
                    client_kwargs["proxy"] = proxy_url
                    async with httpx.AsyncClient(**client_kwargs) as client:
                        resp = await client.post(url, json=payload)
                        resp.raise_for_status()
                except TypeError:
                    # Older httpx: fall back to 'proxies'
                    client_kwargs.pop("proxy", None)
                    client_kwargs["proxies"] = proxies
                    async with httpx.AsyncClient(**client_kwargs) as client:
                        resp = await client.post(url, json=payload)
                        resp.raise_for_status()
            else:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
            logger.info("Registered with center %s as %s", _CENTRAL_API_URL, advertise_url)
            return
        except Exception as exc:
            wait = attempt * 3
            logger.warning("Registration attempt %d failed: %s — retrying in %ds", attempt, exc, wait)
            await asyncio.sleep(wait)
    logger.error("Could not register with center after 5 attempts")


async def _handle_ws_collect(ws, msg: dict) -> None:
    """Execute a collect task received over the WS channel and send back the result."""
    request_id = msg.get("request_id", "")
    req = CollectRequest(
        site=msg.get("site", ""),
        command=msg.get("command", ""),
        args=msg.get("args", {}),
        format=msg.get("format", "json"),
        mode=msg.get("mode", "bridge"),
    )
    try:
        result = await collect(req)
    except Exception as exc:
        logger.exception("WS collect error for request_id=%s: %s", request_id, exc)
        result = {"success": False, "items": [], "error": str(exc)}
    result["type"] = "result"
    result["request_id"] = request_id
    try:
        await ws.send(json.dumps(result))
    except Exception as exc:
        logger.error("WS: failed to send result for request_id=%s: %s", request_id, exc)


async def _register_via_ws(advertise_url: str) -> None:
    """Initiate persistent reverse WebSocket to center and handle collect tasks.

    Keeps reconnecting with exponential back-off so transient outages are
    recovered automatically.  The loop exits only when the process shuts down.
    """
    import websockets  # requires: pip install websockets

    ws_url = (
        _CENTRAL_API_URL
        .replace("https://", "wss://")
        .replace("http://", "ws://")
        .rstrip("/")
        + "/api/v1/nodes/ws"
    )
    _proxy = _HTTPS_PROXY or _HTTP_PROXY or None
    register_payload = json.dumps({
        "type": "register",
        "agent_url": advertise_url,
        "mode": _AGENT_MODE,
        "label": _AGENT_LABEL,
    })

    attempt = 0
    while True:
        attempt += 1
        try:
            logger.info("WS connecting to center %s (attempt %d)", ws_url, attempt)
            connect_kwargs: dict = {"ping_interval": 30, "ping_timeout": 10}
            if _proxy:
                connect_kwargs["proxy"] = _proxy
            async with websockets.connect(ws_url, **connect_kwargs) as ws:
                attempt = 0  # reset on successful connect
                await ws.send(register_payload)

                ack_raw = await asyncio.wait_for(ws.recv(), timeout=15)
                ack = json.loads(ack_raw)
                if ack.get("type") != "registered":
                    raise RuntimeError(f"Unexpected handshake response: {ack}")
                logger.info("WS registered with center as %s", advertise_url)

                # Main receive loop
                async for raw_msg in ws:
                    try:
                        msg = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        logger.warning("WS: invalid JSON from center: %r", raw_msg[:200])
                        continue
                    msg_type = msg.get("type")
                    if msg_type == "collect":
                        asyncio.create_task(_handle_ws_collect(ws, msg))
                    elif msg_type == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                    elif msg_type == "pong":
                        pass
                    else:
                        logger.debug("WS: unknown message type %r", msg_type)

        except asyncio.CancelledError:
            logger.info("WS registration task cancelled — shutting down")
            return
        except Exception as exc:
            wait = min(attempt * 3, 60)
            logger.warning("WS connection lost (attempt %d): %s — reconnecting in %ds",
                           attempt, exc, wait)
            await asyncio.sleep(wait)


_ws_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ws_task
    if not _CENTRAL_API_URL or _AGENT_REGISTER == "off":
        logger.info("Auto-registration disabled (CENTRAL_API_URL=%r AGENT_REGISTER=%s)",
                    _CENTRAL_API_URL or "", _AGENT_REGISTER)
    elif _AGENT_REGISTER == "http":
        advertise_url = _detect_advertise_url()
        logger.info("LAN registration: advertise_url=%s → center=%s", advertise_url, _CENTRAL_API_URL)
        asyncio.get_event_loop().create_task(_register_with_center(advertise_url))
    elif _AGENT_REGISTER == "ws":
        advertise_url = _detect_advertise_url()
        logger.info("WS registration: advertise_url=%s → center=%s", advertise_url, _CENTRAL_API_URL)
        _ws_task = asyncio.get_event_loop().create_task(_register_via_ws(advertise_url))
    yield
    if _ws_task and not _ws_task.done():
        _ws_task.cancel()
        try:
            await _ws_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="OpenCLI Agent Server", version="0.1.0", lifespan=lifespan)


class CollectRequest(BaseModel):
    site: str
    command: str
    args: dict[str, Any] = {}
    format: str = "json"
    mode: str = "bridge"
    # CDP endpoint override; falls back to OPENCLI_CDP_ENDPOINT env var
    cdp_endpoint: str = ""


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


def _parse_output(raw: str, fmt: str) -> list[dict]:
    if fmt == "json":
        start = next((i for i, c in enumerate(raw) if c in "{["), None)
        if start is None:
            raise ValueError(f"No JSON found: {raw[:200]!r}")
        data = json.loads(raw[start:])
        return data if isinstance(data, list) else [data]
    if fmt == "yaml":
        data = yaml.safe_load(raw)
        if isinstance(data, list):
            return data
        return [data] if isinstance(data, dict) else [{"content": str(data)}]
    if fmt == "csv":
        return list(csv.DictReader(io.StringIO(raw.strip())))
    return [{"content": raw}]


@app.get("/health")
def health() -> dict:
    bridge_ok = os.path.isfile(_BRIDGE_BIN)
    cdp_ok = os.path.isfile(_CDP_BIN)
    return {
        "status": "ok",
        "bridge_bin": _BRIDGE_BIN,
        "bridge_bin_exists": bridge_ok,
        "cdp_bin": _CDP_BIN,
        "cdp_bin_exists": cdp_ok,
        "default_cdp_endpoint": _DEFAULT_CDP,
    }


@app.post("/collect")
async def collect(req: CollectRequest) -> dict:
    cdp_ep = req.cdp_endpoint.strip() or _DEFAULT_CDP
    mode = req.mode

    bin_path = _BRIDGE_BIN if mode == "bridge" else _CDP_BIN
    if not os.path.isfile(bin_path):
        # fallback to whichever binary exists
        bin_path = _BRIDGE_BIN if os.path.isfile(_BRIDGE_BIN) else _CDP_BIN

    cmd = [bin_path, req.site, req.command]
    for k, v in req.args.items():
        cmd.extend([f"--{k}", str(v)])
    cmd.extend(["-f", req.format])

    env = os.environ.copy()
    if mode == "bridge":
        hostname = urlparse(cdp_ep).hostname or "localhost"
        env.pop("OPENCLI_CDP_ENDPOINT", None)
        env["OPENCLI_DAEMON_HOST"] = hostname
        env["OPENCLI_DAEMON_PORT"] = str(_DAEMON_PORT)
        logger.info("bridge | cmd=%s daemon=%s:%s", " ".join(cmd), hostname, _DAEMON_PORT)
    else:
        env["OPENCLI_CDP_ENDPOINT"] = cdp_ep
        logger.info("cdp | cmd=%s cdp=%s", " ".join(cmd), cdp_ep)

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_OPENCLI_TIMEOUT)
        rc = proc.returncode
    except asyncio.TimeoutError:
        logger.error("timeout | cmd=%s", " ".join(cmd))
        if proc:
            proc.kill()
            await proc.wait()
        if mode == "cdp":
            await _cleanup_cdp_tabs(cdp_ep)
        return {"success": False, "items": [], "error": "opencli timed out after 120s"}
    except Exception as exc:
        logger.exception("subprocess error | %s", exc)
        if mode == "cdp":
            await _cleanup_cdp_tabs(cdp_ep)
        return {"success": False, "items": [], "error": str(exc)}

    if mode == "cdp":
        await _cleanup_cdp_tabs(cdp_ep)

    stderr_str = stderr.decode().strip()
    stdout_str = stdout.decode()

    if stderr_str:
        logger.warning("stderr | %s", stderr_str[:500])
    if rc != 0:
        logger.error("exit=%d | %s", rc, stderr_str[:500])
        return {"success": False, "items": [], "error": f"opencli exit {rc}: {stderr_str}"}

    try:
        items = _parse_output(stdout_str, req.format)
    except Exception as exc:
        logger.error("parse error | %s", exc)
        return {"success": False, "items": [], "error": f"parse error: {exc}"}

    logger.info("done | site=%s cmd=%s items=%d", req.site, req.command, len(items))
    return {"success": True, "items": items, "error": None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=_AGENT_PORT, log_level="info")
