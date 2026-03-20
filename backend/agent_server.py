"""OpenCLI Agent Server — runs on LAN edge Chrome nodes.

Accepts HTTP POST /collect requests from the center API, executes opencli
locally (pointing at the node's own Chrome instance), and returns results.
The center does NOT need a persistent connection; each request is independent.

On startup, if CENTRAL_API_URL is configured the agent automatically registers
itself with the center — no manual URL entry required.

Usage on the edge node:
    pip install fastapi uvicorn httpx pyyaml
    python -m backend.agent_server
    # or standalone:
    uvicorn backend.agent_server:app --host 0.0.0.0 --port 19823

Environment variables:
    AGENT_PORT              HTTP port to listen on (default: 19823)
    AGENT_ADVERTISE_URL     URL the center should use to reach this agent
                            (default: auto-detected from outbound IP)
    AGENT_MODE              Collection mode reported to center: bridge | cdp (default: bridge)
    AGENT_LABEL             Human-readable label for this agent (default: hostname)
    CENTRAL_API_URL         Center API base URL for self-registration
                            e.g. http://192.168.1.1:8031
                            Leave empty to skip auto-registration.
    OPENCLI_BRIDGE_BIN      Path to opencli 1.0 binary (default: /opt/opencli-bridge/bin/opencli)
    OPENCLI_CDP_BIN         Path to opencli 0.9 binary (default: /opt/opencli-cdp/bin/opencli)
    OPENCLI_CDP_ENDPOINT    Default Chrome CDP endpoint (default: http://localhost:19222)
    OPENCLI_DAEMON_PORT     Bridge daemon port (default: 19825)
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


async def _register_with_center(advertise_url: str) -> None:
    """POST agent registration to the center API. Retries up to 5 times."""
    import httpx

    url = f"{_CENTRAL_API_URL}/api/v1/browsers/agents/register"
    payload = {"agent_url": advertise_url, "mode": _AGENT_MODE, "label": _AGENT_LABEL}

    for attempt in range(1, 6):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            logger.info("Registered with center %s as %s", _CENTRAL_API_URL, advertise_url)
            return
        except Exception as exc:
            wait = attempt * 3
            logger.warning("Registration attempt %d failed: %s — retrying in %ds", attempt, exc, wait)
            await asyncio.sleep(wait)
    logger.error("Could not register with center after 5 attempts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _CENTRAL_API_URL:
        advertise_url = _detect_advertise_url()
        logger.info("Auto-registration enabled: advertise_url=%s center=%s", advertise_url, _CENTRAL_API_URL)
        asyncio.get_event_loop().create_task(_register_with_center(advertise_url))
    else:
        logger.info("CENTRAL_API_URL not set — skipping auto-registration")
    yield


app = FastAPI(title="OpenCLI Agent Server", version="0.1.0", lifespan=lifespan)


class CollectRequest(BaseModel):
    site: str
    command: str
    args: dict[str, Any] = {}
    format: str = "json"
    mode: str = "bridge"
    # CDP endpoint override; falls back to OPENCLI_CDP_ENDPOINT env var
    cdp_endpoint: str = ""


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

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        rc = proc.returncode
    except asyncio.TimeoutError:
        logger.error("timeout | cmd=%s", " ".join(cmd))
        return {"success": False, "items": [], "error": "opencli timed out after 120s"}
    except Exception as exc:
        logger.exception("subprocess error | %s", exc)
        return {"success": False, "items": [], "error": str(exc)}

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
