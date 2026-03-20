"""Edge node management API.

Handles registration, lifecycle events, and management of remote agent nodes.
Both HTTP-mode agents (center calls agent) and WS-mode agents (agent initiates
reverse channel) register here and have their online/offline history tracked.
"""

import asyncio
import logging
import socket
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.schemas.edge_node import EdgeNodeRead, EdgeNodeEventRead

router = APIRouter(prefix="/nodes", tags=["nodes"])
logger = logging.getLogger(__name__)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _upsert_node(
    db: AsyncSession,
    url: str,
    label: str = "",
    protocol: str = "http",
    mode: str = "bridge",
    ip: str | None = None,
) -> "EdgeNode":  # type: ignore[name-defined]
    from backend.models.edge_node import EdgeNode

    result = await db.execute(select(EdgeNode).where(EdgeNode.url == url))
    node = result.scalar_one_or_none()
    now = _utcnow()
    if node:
        node.status = "online"
        node.last_seen_at = now
        node.protocol = protocol
        node.mode = mode
        if label:
            node.label = label
        if ip:
            node.ip = ip
    else:
        node = EdgeNode(
            url=url,
            label=label or url,
            protocol=protocol,
            mode=mode,
            status="online",
            last_seen_at=now,
            ip=ip,
        )
        db.add(node)
    await db.flush()
    return node


async def _write_event(
    db: AsyncSession,
    node_id: str,
    event: str,
    ip: str | None = None,
    event_meta: dict | None = None,
) -> None:
    from backend.models.edge_node import EdgeNodeEvent

    db.add(EdgeNodeEvent(node_id=node_id, event=event, ip=ip, event_meta=event_meta))
    await db.flush()


def _pool_add(url: str, mode: str, protocol: str) -> None:
    """Hot-add a node URL to the in-memory browser pool."""
    try:
        from backend.browser_pool import get_pool, LocalBrowserPool
        pool = get_pool()
        if isinstance(pool, LocalBrowserPool):
            if url not in pool.endpoints:
                pool.add_endpoint(url)
            pool.set_mode(url, mode)
            pool.set_agent_url(url, url)
            pool.set_agent_protocol(url, protocol)
    except Exception as exc:
        logger.warning("pool_add failed for %s: %s", url, exc)


def _pool_remove(url: str) -> None:
    try:
        from backend.browser_pool import get_pool, LocalBrowserPool
        pool = get_pool()
        if isinstance(pool, LocalBrowserPool) and url in pool.endpoints:
            pool.remove_endpoint(url)
    except Exception as exc:
        logger.warning("pool_remove failed for %s: %s", url, exc)


def _extract_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


# ── Registration (HTTP mode) ──────────────────────────────────────────────────

from pydantic import BaseModel


class NodeRegisterRequest(BaseModel):
    agent_url: str
    mode: str = "bridge"
    label: str = ""
    agent_protocol: str = "http"


@router.post("/register", response_model=ApiResponse[EdgeNodeRead])
async def register_node(
    body: NodeRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Agent self-registration (HTTP mode).

    Agent POSTs its own URL; center adds it to the pool and records the event.
    Idempotent: calling again updates mode/label and records an 'online' event.
    """
    from backend.models.browser import BrowserInstance

    url = body.agent_url.rstrip("/")
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="agent_url must be an http/https URL")
    if body.mode not in ("bridge", "cdp"):
        raise HTTPException(status_code=400, detail="mode must be 'bridge' or 'cdp'")
    if body.agent_protocol not in ("http", "ws"):
        raise HTTPException(status_code=400, detail="agent_protocol must be 'http' or 'ws'")

    ip = _extract_ip(request)
    node = await _upsert_node(db, url, body.label, body.agent_protocol, body.mode, ip)
    is_new = node.id not in {r.id for r in []}  # always write event
    await _write_event(db, node.id, "registered", ip=ip,
                       event_meta={"mode": body.mode, "protocol": body.agent_protocol})

    # Maintain backwards-compatible BrowserInstance record for pool config
    result = await db.execute(
        select(BrowserInstance).where(BrowserInstance.endpoint == url)
    )
    inst = result.scalar_one_or_none()
    if inst:
        inst.mode = body.mode
        inst.agent_url = url
        inst.agent_protocol = body.agent_protocol
        if body.label:
            inst.label = body.label
    else:
        inst = BrowserInstance(
            endpoint=url, mode=body.mode,
            agent_url=url, agent_protocol=body.agent_protocol, label=body.label,
        )
        db.add(inst)

    await db.commit()
    await db.refresh(node)

    _pool_add(url, body.mode, body.agent_protocol)
    logger.info("Node registered (HTTP): %s (mode=%s label=%r)", url, body.mode, body.label)
    return ApiResponse.ok(EdgeNodeRead.model_validate(node))


# ── Node list & events ────────────────────────────────────────────────────────

@router.get("", response_model=ApiResponse[list[EdgeNodeRead]])
async def list_nodes(db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """List all registered edge nodes, with real-time WS online status overlaid."""
    from backend.models.edge_node import EdgeNode
    from backend import ws_agent_manager

    result = await db.execute(select(EdgeNode).order_by(EdgeNode.created_at))
    nodes = result.scalars().all()

    ws_connected = set(ws_agent_manager.list_connected())
    out = []
    for node in nodes:
        data = EdgeNodeRead.model_validate(node)
        # WS-connected nodes are always "online" regardless of DB status
        if node.protocol == "ws" and node.url in ws_connected:
            data = data.model_copy(update={"status": "online"})
        out.append(data)
    return ApiResponse.ok(out)


@router.get("/{node_id}/events", response_model=ApiResponse[list[EdgeNodeEventRead]])
async def list_node_events(node_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """Return the last 100 lifecycle events for a node."""
    from backend.models.edge_node import EdgeNode, EdgeNodeEvent

    result = await db.execute(select(EdgeNode).where(EdgeNode.id == node_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Node not found")

    result = await db.execute(
        select(EdgeNodeEvent)
        .where(EdgeNodeEvent.node_id == node_id)
        .order_by(EdgeNodeEvent.created_at.desc())
        .limit(100)
    )
    events = result.scalars().all()
    return ApiResponse.ok([EdgeNodeEventRead.model_validate(e) for e in events])


@router.delete("/{node_id}", response_model=ApiResponse[None])
async def delete_node(node_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """Remove a node from the DB and from the in-memory pool."""
    from backend.models.edge_node import EdgeNode

    result = await db.execute(select(EdgeNode).where(EdgeNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    _pool_remove(node.url)

    # Also remove BrowserInstance record
    from backend.models.browser import BrowserInstance
    bi_result = await db.execute(
        select(BrowserInstance).where(BrowserInstance.endpoint == node.url)
    )
    bi = bi_result.scalar_one_or_none()
    if bi:
        await db.delete(bi)

    await db.delete(node)
    await db.commit()
    logger.info("Node deleted: %s", node.url)
    return ApiResponse.ok(None)


# ── Install script ────────────────────────────────────────────────────────────

@router.get("/install/agent.sh", response_class=PlainTextResponse)
async def get_install_script(request: Request) -> PlainTextResponse:
    """Return the agent install script with CENTRAL_API_URL pre-filled.

    URL resolution priority:
    1. PUBLIC_URL env var (most reliable, admin-configured)
    2. X-Forwarded-Host / X-Forwarded-Proto headers (reverse proxy)
    3. Host header + scheme (direct access)
    4. request.base_url fallback (may be internal when behind changeOrigin proxy)
    """
    from backend.config import get_settings
    settings = get_settings()

    if settings.public_url:
        base_url = settings.public_url.rstrip("/")
    else:
        # Try to reconstruct from proxy headers (nginx, Vite proxy, etc.)
        forwarded_host = request.headers.get("x-forwarded-host", "")
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        host = request.headers.get("host", "")

        if forwarded_host:
            proto = forwarded_proto or ("https" if "443" in forwarded_host else "http")
            base_url = f"{proto}://{forwarded_host}"
        elif host and not host.startswith(("api:", "localhost:800", "127.0.0.1:800")):
            # Host is the original client-visible host (not an internal service name)
            proto = "https" if request.url.scheme == "https" else "http"
            base_url = f"{proto}://{host}"
        else:
            # Last resort: request.base_url (may be internal in Docker)
            base_url = str(request.base_url).rstrip("/")

    # Try file path first (local dev where scripts/ is accessible)
    for candidate in [
        Path(__file__).parent.parent.parent.parent / "scripts" / "install-agent.sh",
        Path("/app/scripts/install-agent.sh"),
    ]:
        if candidate.exists():
            content = candidate.read_text()
            content = content.replace("__CENTRAL_API_URL__", base_url)
            return PlainTextResponse(content, media_type="text/plain")

    # Inline fallback (Docker: only ./backend is mounted)
    content = _install_script_template(base_url)
    return PlainTextResponse(content, media_type="text/plain")


def _install_script_template(central_url: str) -> str:
    return f'''#!/usr/bin/env bash
# OpenCLI Agent — one-line install
# Usage: curl -fsSL {central_url}/api/v1/nodes/install/agent.sh | bash
# Or:    curl -fsSL {central_url}/api/v1/nodes/install/agent.sh | AGENT_REGISTER=ws bash

set -euo pipefail
CENTRAL_API_URL="${{CENTRAL_API_URL:-{central_url}}}"
AGENT_REGISTER="${{AGENT_REGISTER:-ws}}"
AGENT_PORT="${{AGENT_PORT:-19823}}"
AGENT_LABEL="${{AGENT_LABEL:-$(hostname)}}"
IMAGE_TAG="${{IMAGE_TAG:-0.1.0}}"
INSTALL_MODE="${{1:-docker}}"

info() {{ printf "\\e[32m[INFO]\\e[0m  %s\\n" "$*"; }}
die()  {{ printf "\\e[31m[ERROR]\\e[0m %s\\n" "$*" >&2; exit 1; }}

[[ -z "$CENTRAL_API_URL" ]] && die "CENTRAL_API_URL is required"
info "Center: $CENTRAL_API_URL | Register: $AGENT_REGISTER | Mode: $INSTALL_MODE"

install_docker() {{
  command -v docker >/dev/null 2>&1 || die "Docker not found"
  CONTAINER_NAME="opencli-agent"
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  OCCUPIED_BY=$(docker ps --format '{{{{.Names}}}} {{{{.Ports}}}}' | grep "0.0.0.0:${{AGENT_PORT}}->" | awk '{{{{print $1}}}}')
  if [[ -n "$OCCUPIED_BY" ]]; then
    printf "\\e[33m[WARN]\\e[0m  Port $AGENT_PORT used by: $OCCUPIED_BY\\n"
    printf "\\e[33m[WARN]\\e[0m  Stop it: docker stop $OCCUPIED_BY\\n"
    printf "\\e[33m[WARN]\\e[0m  Or use a different port: AGENT_PORT=19824 bash $0\\n"
    die "Port conflict"
  fi
  PROXY_ARGS=""
  [[ -n "${{HTTP_PROXY:-}}" ]]  && PROXY_ARGS="$PROXY_ARGS -e HTTP_PROXY=$HTTP_PROXY"
  [[ -n "${{HTTPS_PROXY:-}}" ]] && PROXY_ARGS="$PROXY_ARGS -e HTTPS_PROXY=$HTTPS_PROXY"
  # shellcheck disable=SC2086
  docker run -d --name "$CONTAINER_NAME" --restart unless-stopped \\
    -e CENTRAL_API_URL="$CENTRAL_API_URL" -e AGENT_REGISTER="$AGENT_REGISTER" \\
    -e AGENT_PORT="$AGENT_PORT" -e AGENT_LABEL="$AGENT_LABEL" -e AGENT_MODE="cdp" \\
    $PROXY_ARGS -p "${{AGENT_PORT}}:${{AGENT_PORT}}" \\
    "xjh1994/opencli-admin-agent:${{IMAGE_TAG}}"
  info "Agent container started!"
}}

install_python() {{
  command -v python3 >/dev/null 2>&1 || die "Python 3 not found"
  pip3 install --quiet fastapi uvicorn httpx pyyaml websockets
  CENTRAL_API_URL="$CENTRAL_API_URL" AGENT_REGISTER="$AGENT_REGISTER" \\
  AGENT_PORT="$AGENT_PORT" AGENT_LABEL="$AGENT_LABEL" AGENT_MODE="cdp" \\
  nohup python3 -m backend.agent_server > /tmp/opencli-agent.log 2>&1 &
  info "Agent started (PID=$!). Logs: /tmp/opencli-agent.log"
}}

case "$INSTALL_MODE" in
  docker) install_docker ;;
  python) install_python ;;
  *) die "Usage: $0 [docker|python]" ;;
esac
info "Done! Nodes will appear at: $CENTRAL_API_URL → 节点管理"
'''


# ── WebSocket reverse channel ─────────────────────────────────────────────────

@router.websocket("/ws")
async def node_ws_endpoint(ws: WebSocket) -> None:
    """Reverse WebSocket channel for NAT/unreachable edge agents.

    Agent initiates this connection, sends a 'register' handshake, then
    listens for 'collect' tasks from the center and sends back 'result' messages.
    """
    from backend import ws_agent_manager
    from backend.database import AsyncSessionLocal
    from backend.models.browser import BrowserInstance

    await ws.accept()
    agent_url: str | None = None

    try:
        # ── 1. Registration handshake ─────────────────────────────────────
        data = await ws.receive_json()
        if data.get("type") != "register":
            await ws.close(code=1008, reason="Expected 'register' message first")
            return

        agent_url = data.get("agent_url", "").rstrip("/")
        mode = data.get("mode", "bridge")
        label = data.get("label", "")

        if not agent_url.startswith("http"):
            await ws.close(code=1008, reason="agent_url must be an http/https URL")
            return
        if mode not in ("bridge", "cdp"):
            await ws.close(code=1008, reason="mode must be 'bridge' or 'cdp'")
            return

        # ── 2. Upsert node + write event ──────────────────────────────────
        try:
            async with AsyncSessionLocal() as db:
                node = await _upsert_node(db, agent_url, label, "ws", mode)
                await _write_event(db, node.id, "online",
                                   event_meta={"mode": mode, "protocol": "ws"})
                # BrowserInstance compat
                result = await db.execute(
                    select(BrowserInstance).where(BrowserInstance.endpoint == agent_url)
                )
                inst = result.scalar_one_or_none()
                if inst:
                    inst.mode = mode
                    inst.agent_url = agent_url
                    inst.agent_protocol = "ws"
                    if label:
                        inst.label = label
                else:
                    inst = BrowserInstance(
                        endpoint=agent_url, mode=mode,
                        agent_url=agent_url, agent_protocol="ws", label=label,
                    )
                    db.add(inst)
                await db.commit()
        except Exception as exc:
            logger.warning("WS node %s: DB upsert failed (non-fatal): %s", agent_url, exc)

        _pool_add(agent_url, mode, "ws")
        ws_agent_manager.register_connection(agent_url, ws)
        await ws.send_json({"type": "registered", "agent_url": agent_url})
        logger.info("WS node registered: %s (mode=%s label=%r)", agent_url, mode, label)

        # ── 3. Receive loop ───────────────────────────────────────────────
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")
            if msg_type == "result":
                ws_agent_manager.resolve_response(msg.get("request_id", ""), msg)
            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})
            else:
                logger.debug("WS node %s: unknown message type %r", agent_url, msg_type)

    except WebSocketDisconnect:
        logger.info("WS node disconnected: %s", agent_url or "<unregistered>")
    except Exception as exc:
        logger.exception("WS node %s: error: %s", agent_url or "<unregistered>", exc)
    finally:
        if agent_url:
            ws_agent_manager.unregister_connection(agent_url)
            # Write offline event
            try:
                async with AsyncSessionLocal() as db:
                    from backend.models.edge_node import EdgeNode
                    result = await db.execute(
                        select(EdgeNode).where(EdgeNode.url == agent_url)
                    )
                    node = result.scalar_one_or_none()
                    if node:
                        node.status = "offline"
                        await _write_event(db, node.id, "offline")
                        await db.commit()
            except Exception as exc:
                logger.warning("WS node %s: offline event write failed: %s", agent_url, exc)
