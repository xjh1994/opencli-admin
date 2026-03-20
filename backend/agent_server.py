"""OpenCLI Agent Server — runs on LAN edge Chrome nodes.

Accepts HTTP POST /collect requests from the center API, executes opencli
locally (pointing at the node's own Chrome instance), and returns results.
The center does NOT need a persistent connection; each request is independent.

Usage on the edge node:
    pip install fastapi uvicorn httpx pyyaml
    python -m backend.agent_server
    # or standalone:
    uvicorn backend.agent_server:app --host 0.0.0.0 --port 19823

Environment variables:
    AGENT_PORT           HTTP port to listen on (default: 19823)
    OPENCLI_BRIDGE_BIN   Path to opencli 1.0 binary (default: /opt/opencli-bridge/bin/opencli)
    OPENCLI_CDP_BIN      Path to opencli 0.9 binary (default: /opt/opencli-cdp/bin/opencli)
    OPENCLI_CDP_ENDPOINT Default Chrome CDP endpoint (default: http://localhost:19222)
    OPENCLI_DAEMON_PORT  Bridge daemon port (default: 19825)
"""

import asyncio
import csv
import io
import json
import logging
import os
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

app = FastAPI(title="OpenCLI Agent Server", version="0.1.0")


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
    port = int(os.environ.get("AGENT_PORT", "19823"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
