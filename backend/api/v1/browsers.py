import asyncio
import logging
import os
import re
import socket

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from pydantic import BaseModel

from backend.schemas.browser import BrowserBindingCreate, BrowserBindingRead, BrowserInstanceRead
from backend.schemas.common import ApiResponse
from backend.services import browser_service

router = APIRouter(prefix="/browsers", tags=["browsers"])
logger = logging.getLogger(__name__)

# ── Bindings ──────────────────────────────────────────────────────────────────

@router.get("/bindings", response_model=ApiResponse[list[BrowserBindingRead]])
async def list_bindings(db: AsyncSession = Depends(get_db)) -> ApiResponse:
    bindings = await browser_service.list_bindings(db)
    return ApiResponse.ok([BrowserBindingRead.model_validate(b) for b in bindings])


@router.post("/bindings", response_model=ApiResponse[BrowserBindingRead])
async def create_binding(
    body: BrowserBindingCreate, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    existing = await browser_service.get_binding_by_site(db, body.site)
    if existing:
        raise HTTPException(status_code=409, detail=f"Site '{body.site}' is already bound")
    binding = await browser_service.create_binding(
        db, body.browser_endpoint, body.site, body.notes
    )
    await db.commit()
    return ApiResponse.ok(BrowserBindingRead.model_validate(binding))


@router.delete("/bindings/{binding_id}", response_model=ApiResponse[None])
async def delete_binding(
    binding_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    deleted = await browser_service.delete_binding(db, binding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Binding not found")
    await db.commit()
    return ApiResponse.ok(None)


# ── Chrome pool management ────────────────────────────────────────────────────

def _docker_client():
    try:
        import docker  # type: ignore[import]
        return docker.from_env()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Docker socket not available: {exc}")


def _project_name() -> str:
    return os.environ.get("COMPOSE_PROJECT_NAME", "opencli-admin")


def _update_env_file(key: str, value: str, path: str = "") -> None:
    if not path:
        path = os.environ.get("ENV_FILE_PATH", "/app/.env")
    """Update or append KEY=value in the .env file."""
    try:
        with open(path) as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    new_line = f"{key}={value}"
    pattern = rf"^{re.escape(key)}=.*$"
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + f"\n{new_line}\n"
    with open(path, "w") as f:
        f.write(content)


@router.post("/chrome-instances", response_model=ApiResponse[dict])
async def add_chrome_instance(
    count: int = 1,
    mode: str = "bridge",
    agent_url: str = "",
    agent_protocol: str = "",
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Start one or more new Chrome instances (chrome-N) and hot-add them to the pool."""
    from backend.browser_pool import get_pool, LocalBrowserPool
    from backend.models.browser import BrowserInstance
    from sqlalchemy import select

    if count < 1 or count > 10:
        raise HTTPException(status_code=400, detail="count must be between 1 and 10")
    if mode not in ("bridge", "cdp"):
        raise HTTPException(status_code=400, detail="mode must be 'bridge' or 'cdp'")
    clean_agent_url = agent_url.strip() or None
    clean_agent_protocol = agent_protocol.strip() or None
    if clean_agent_protocol and clean_agent_protocol not in ("http", "ws"):
        raise HTTPException(status_code=400, detail="agent_protocol must be 'http' or 'ws'")

    pool = get_pool()
    project = _project_name()
    novnc_base = int(os.environ.get("NOVNC_BASE_PORT", 3010))
    network = f"{project}_default"
    image = f"{project}-chrome"
    client = _docker_client()

    created: list[dict] = []
    for _ in range(count):
        current = pool.endpoints
        N = len(current) + 1
        name = f"agent-{N}"
        novnc_port = novnc_base + N - 1
        volume = f"{project}_agent_profile_{N}"
        new_endpoint = f"http://{name}:19222"

        try:
            existing = client.containers.get(name)
            if existing.status != "running":
                existing.start()
                logger.info("agent-pool: restarted existing container %s", name)
            else:
                logger.info("agent-pool: %s already running", name)
        except Exception:
            try:
                client.containers.run(
                    image,
                    detach=True,
                    name=name,
                    network=network,
                    labels={"agent.pool.extra": "true", "agent.pool.index": str(N)},
                    ports={"6080/tcp": novnc_port},
                    volumes={volume: {"bind": "/home/chrome/.config/chromium", "mode": "rw"}},
                    restart_policy={"Name": "unless-stopped"},
                )
                logger.info("agent-pool: started new container %s on noVNC :%d", name, novnc_port)
            except Exception as exc:
                logger.exception("agent-pool: failed to start %s", name)
                raise HTTPException(status_code=500, detail=str(exc))

        if isinstance(pool, LocalBrowserPool) and new_endpoint not in pool.endpoints:
            pool.add_endpoint(new_endpoint)
        pool.set_mode(new_endpoint, mode)
        if isinstance(pool, LocalBrowserPool):
            pool.set_agent_url(new_endpoint, clean_agent_url)
            pool.set_agent_protocol(new_endpoint, clean_agent_protocol)

        # Persist to DB
        result = await db.execute(select(BrowserInstance).where(BrowserInstance.endpoint == new_endpoint))
        inst = result.scalar_one_or_none()
        if inst:
            inst.mode = mode
            inst.agent_url = clean_agent_url
            inst.agent_protocol = clean_agent_protocol
        else:
            inst = BrowserInstance(endpoint=new_endpoint, mode=mode,
                                   agent_url=clean_agent_url, agent_protocol=clean_agent_protocol, label="")
            db.add(inst)

        created.append({"endpoint": new_endpoint, "novnc_port": novnc_port})

    await db.commit()

    all_endpoints = ",".join(pool.endpoints)
    try:
        _update_env_file("AGENT_POOL_ENDPOINTS", all_endpoints)
    except Exception as exc:
        logger.warning("agent-pool: could not update .env: %s", exc)

    return ApiResponse.ok({
        "created": created,
        "total": len(pool.endpoints),
    })


class AgentRegisterRequest(BaseModel):
    agent_url: str                  # e.g. http://192.168.1.100:19823
    mode: str = "bridge"            # bridge | cdp
    label: str = ""
    agent_protocol: str = "http"    # http | ws


@router.post("/agents/register", response_model=ApiResponse[BrowserInstanceRead])
async def register_agent(
    body: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Agent self-registration: agent POSTs its own URL, center adds it to the pool.

    The agent_url is used as the pool endpoint (logical key for routing).
    Idempotent: calling again with the same agent_url updates mode/label.
    """
    from backend.browser_pool import get_pool, LocalBrowserPool
    from backend.models.browser import BrowserInstance

    agent_url = body.agent_url.rstrip("/")
    if not agent_url.startswith("http"):
        raise HTTPException(status_code=400, detail="agent_url must be an http/https URL")
    if body.mode not in ("bridge", "cdp"):
        raise HTTPException(status_code=400, detail="mode must be 'bridge' or 'cdp'")
    if body.agent_protocol not in ("http", "ws"):
        raise HTTPException(status_code=400, detail="agent_protocol must be 'http' or 'ws'")

    pool = get_pool()

    # Add to pool if not already present (agent_url is the pool endpoint key)
    if isinstance(pool, LocalBrowserPool):
        if agent_url not in pool.endpoints:
            pool.add_endpoint(agent_url)
        pool.set_mode(agent_url, body.mode)
        pool.set_agent_url(agent_url, agent_url)
        pool.set_agent_protocol(agent_url, body.agent_protocol)

    # Upsert in DB
    result = await db.execute(select(BrowserInstance).where(BrowserInstance.endpoint == agent_url))
    inst = result.scalar_one_or_none()
    if inst:
        inst.mode = body.mode
        inst.agent_url = agent_url
        inst.agent_protocol = body.agent_protocol
        if body.label:
            inst.label = body.label
    else:
        inst = BrowserInstance(
            endpoint=agent_url, mode=body.mode,
            agent_url=agent_url, agent_protocol=body.agent_protocol, label=body.label,
        )
        db.add(inst)
    await db.commit()
    await db.refresh(inst)

    # Also upsert EdgeNode so the Nodes UI can see HTTP-registered agents
    try:
        from backend.models.edge_node import EdgeNode, EdgeNodeEvent
        from datetime import datetime, timezone
        _now = datetime.now(timezone.utc)
        result2 = await db.execute(select(EdgeNode).where(EdgeNode.url == agent_url))
        node = result2.scalar_one_or_none()
        if node:
            node.status = "online"
            node.last_seen_at = _now
            node.protocol = "http"
            node.mode = body.mode
            if body.label:
                node.label = body.label
        else:
            node = EdgeNode(
                url=agent_url, label=body.label or agent_url,
                protocol="http", mode=body.mode, status="online",
                last_seen_at=_now,
            )
            db.add(node)
            await db.flush()
            db.add(EdgeNodeEvent(node_id=node.id, event="registered"))
        await db.commit()
    except Exception as exc:
        logger.warning("Agent %s: EdgeNode upsert failed (non-fatal): %s", agent_url, exc)

    logger.info("Agent registered: %s (mode=%s)", agent_url, body.mode)
    return ApiResponse.ok(BrowserInstanceRead.model_validate(inst))


class InstanceConfigUpdate(BaseModel):
    mode: str | None = None
    agent_url: str | None = None
    agent_protocol: str | None = None


@router.patch("/instances/{endpoint_b64}", response_model=ApiResponse[BrowserInstanceRead])
async def update_instance_config(
    endpoint_b64: str,
    body: InstanceConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Update mode or agent_url for a Chrome pool instance."""
    import base64
    from backend.browser_pool import get_pool, LocalBrowserPool

    try:
        padded = endpoint_b64 + "=" * (-len(endpoint_b64) % 4)
        endpoint = base64.urlsafe_b64decode(padded.encode()).decode()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid endpoint encoding")

    pool = get_pool()
    if endpoint not in pool.endpoints:
        raise HTTPException(status_code=404, detail=f"Endpoint {endpoint!r} not in pool")

    if body.mode is not None:
        if body.mode not in ("bridge", "cdp"):
            raise HTTPException(status_code=400, detail="mode must be 'bridge' or 'cdp'")
        pool.set_mode(endpoint, body.mode)

    fields_set = body.model_fields_set

    clean_agent_url = body.agent_url.strip() if body.agent_url else None
    if "agent_url" in fields_set and isinstance(pool, LocalBrowserPool):
        pool.set_agent_url(endpoint, clean_agent_url or None)

    if "agent_protocol" in fields_set:
        if body.agent_protocol is not None and body.agent_protocol not in ("http", "ws"):
            raise HTTPException(status_code=400, detail="agent_protocol must be 'http' or 'ws'")
        if isinstance(pool, LocalBrowserPool):
            pool.set_agent_protocol(endpoint, body.agent_protocol)

    from backend.models.browser import BrowserInstance
    result = await db.execute(select(BrowserInstance).where(BrowserInstance.endpoint == endpoint))
    inst = result.scalar_one_or_none()
    if inst is None:
        inst = BrowserInstance(endpoint=endpoint, mode=pool.get_mode(endpoint), label="")
        db.add(inst)
    if body.mode is not None:
        inst.mode = body.mode
    if "agent_url" in fields_set:
        inst.agent_url = clean_agent_url or None
    if "agent_protocol" in fields_set:
        inst.agent_protocol = body.agent_protocol
    await db.commit()
    await db.refresh(inst)

    return ApiResponse.ok(BrowserInstanceRead.model_validate(inst))


@router.delete("/instances/{endpoint_b64}", response_model=ApiResponse[dict])
async def remove_instance(
    endpoint_b64: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Remove any pool entry by endpoint URL (base64-encoded). Does NOT touch Docker containers."""
    import base64
    from backend.browser_pool import get_pool, LocalBrowserPool
    from backend.models.browser import BrowserInstance

    try:
        padded = endpoint_b64 + "=" * (-len(endpoint_b64) % 4)
        endpoint = base64.urlsafe_b64decode(padded.encode()).decode()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid endpoint encoding")

    pool = get_pool()
    if endpoint not in pool.endpoints:
        raise HTTPException(status_code=404, detail=f"Endpoint {endpoint!r} not in pool")

    if isinstance(pool, LocalBrowserPool):
        pool.remove_endpoint(endpoint)

    result = await db.execute(select(BrowserInstance).where(BrowserInstance.endpoint == endpoint))
    inst = result.scalar_one_or_none()
    if inst:
        await db.delete(inst)
        await db.commit()

    logger.info("Removed pool entry: %s", endpoint)
    return ApiResponse.ok({"removed": endpoint, "total": len(pool.endpoints)})


@router.delete("/chrome-instances/{n}", response_model=ApiResponse[dict])
async def remove_chrome_instance(n: int) -> ApiResponse:
    """Stop and remove agent-N (N >= 2). Instance 1 is managed by docker-compose."""
    if n < 2:
        raise HTTPException(status_code=400, detail="Instance 1 is managed by docker-compose")

    from backend.browser_pool import get_pool, LocalBrowserPool

    pool = get_pool()
    name = f"agent-{n}"
    endpoint = f"http://{name}:19222"

    client = _docker_client()
    try:
        container = client.containers.get(name)
        container.remove(force=True)
        logger.info("agent-pool: removed container %s", name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Container {name} not found: {exc}")

    if isinstance(pool, LocalBrowserPool):
        pool.remove_endpoint(endpoint)

    all_endpoints = ",".join(ep for ep in pool.endpoints if ep != endpoint)
    try:
        _update_env_file("AGENT_POOL_ENDPOINTS", all_endpoints)
    except Exception as exc:
        logger.warning("agent-pool: could not update .env: %s", exc)

    return ApiResponse.ok({"removed": name, "total": len(pool.endpoints)})


@router.get("/agents/ws-status", response_model=ApiResponse[dict])
async def ws_agents_status() -> ApiResponse:
    """Return the list of agent URLs that currently have an active WS connection."""
    from backend import ws_agent_manager

    connected = ws_agent_manager.list_connected()
    return ApiResponse.ok({"connected": connected})


@router.websocket("/agents/ws")
async def agent_ws_endpoint(ws: WebSocket) -> None:
    """Reverse WebSocket channel for NAT/unreachable edge agents.

    The agent initiates this connection, sends a 'register' handshake, then
    listens for 'collect' tasks from the center and sends back 'result' messages.
    The center keeps the connection alive and uses it to dispatch collect requests.
    """
    from backend import ws_agent_manager
    from backend.browser_pool import get_pool, LocalBrowserPool
    from backend.models.browser import BrowserInstance

    await ws.accept()
    agent_url: str | None = None

    try:
        # ── 1. Registration handshake ─────────────────────────────────────────
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

        # ── 2. Add/update in pool ─────────────────────────────────────────────
        pool = get_pool()
        if isinstance(pool, LocalBrowserPool):
            if agent_url not in pool.endpoints:
                pool.add_endpoint(agent_url)
            pool.set_mode(agent_url, mode)
            pool.set_agent_url(agent_url, agent_url)
            pool.set_agent_protocol(agent_url, "ws")

        # Upsert in DB (fire-and-forget; don't block the WS receive loop)
        try:
            from backend.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
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
            logger.warning("WS agent %s: DB upsert failed (non-fatal): %s", agent_url, exc)

        # Also upsert into EdgeNode so the Nodes UI can see this agent
        try:
            from backend.models.edge_node import EdgeNode, EdgeNodeEvent
            from backend.database import AsyncSessionLocal
            from datetime import datetime, timezone
            _now = datetime.now(timezone.utc)
            async with AsyncSessionLocal() as _db:
                from sqlalchemy import select as _select
                _res = await _db.execute(_select(EdgeNode).where(EdgeNode.url == agent_url))
                _node = _res.scalar_one_or_none()
                if _node:
                    _node.status = "online"
                    _node.last_seen_at = _now
                    _node.protocol = "ws"
                    _node.mode = mode
                    if label:
                        _node.label = label
                else:
                    _node = EdgeNode(
                        url=agent_url, label=label or agent_url,
                        protocol="ws", mode=mode, status="online",
                        last_seen_at=_now,
                    )
                    _db.add(_node)
                    await _db.flush()
                    _db.add(EdgeNodeEvent(node_id=_node.id, event="registered"))
                await _db.commit()
        except Exception as _exc:
            logger.warning("WS agent %s: EdgeNode upsert failed (non-fatal): %s", agent_url, _exc)

        ws_agent_manager.register_connection(agent_url, ws)
        await ws.send_json({"type": "registered", "agent_url": agent_url})
        logger.info("WS agent registered: %s (mode=%s label=%r)", agent_url, mode, label)

        # ── 3. Receive loop: results + pings ──────────────────────────────────
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")
            if msg_type == "result":
                ws_agent_manager.resolve_response(msg.get("request_id", ""), msg)
            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})
            else:
                logger.debug("WS agent %s: unknown message type %r", agent_url, msg_type)

    except WebSocketDisconnect:
        logger.info("WS agent disconnected: %s", agent_url or "<unregistered>")
    except Exception as exc:
        logger.exception("WS agent %s: unexpected error: %s", agent_url or "<unregistered>", exc)
    finally:
        if agent_url:
            ws_agent_manager.unregister_connection(agent_url)
            try:
                from backend.models.edge_node import EdgeNode, EdgeNodeEvent
                from backend.database import AsyncSessionLocal
                from datetime import datetime, timezone
                from sqlalchemy import select as _select
                async with AsyncSessionLocal() as _db:
                    _res = await _db.execute(_select(EdgeNode).where(EdgeNode.url == agent_url))
                    _node = _res.scalar_one_or_none()
                    if _node:
                        _node.status = "offline"
                        _node.last_seen_at = datetime.now(timezone.utc)
                        _db.add(EdgeNodeEvent(node_id=_node.id, event="offline"))
                        await _db.commit()
            except Exception as _exc:
                logger.warning("WS agent %s: EdgeNode offline update failed: %s", agent_url, _exc)


@router.post("/restart-api", response_model=ApiResponse[dict])
async def restart_api() -> ApiResponse:
    """Restart the API container (e.g. after manually editing .env)."""
    container_id = socket.gethostname()
    client = _docker_client()
    try:
        container = client.containers.get(container_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not find own container: {exc}")

    logger.info("API restart requested — restarting container %s in 1s", container_id)
    # Delay restart so the HTTP response can be sent first
    asyncio.get_event_loop().call_later(1.0, container.restart)
    return ApiResponse.ok({"restarting": True, "container": container_id})
