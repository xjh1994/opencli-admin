import asyncio
import logging
import os
import re
import socket

from fastapi import APIRouter, Depends, HTTPException
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


def _update_env_file(key: str, value: str, path: str = "/app/.env") -> None:
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
        name = f"chrome-{N}"
        novnc_port = novnc_base + N - 1
        volume = f"{project}_chrome_profile_{N}"
        new_endpoint = f"http://{name}:19222"

        try:
            existing = client.containers.get(name)
            if existing.status != "running":
                existing.start()
                logger.info("chrome-pool: restarted existing container %s", name)
            else:
                logger.info("chrome-pool: %s already running", name)
        except Exception:
            try:
                client.containers.run(
                    image,
                    detach=True,
                    name=name,
                    network=network,
                    labels={"chrome.pool.extra": "true", "chrome.pool.index": str(N)},
                    ports={"6080/tcp": novnc_port},
                    volumes={volume: {"bind": "/home/chrome/.config/chromium", "mode": "rw"}},
                    restart_policy={"Name": "unless-stopped"},
                )
                logger.info("chrome-pool: started new container %s on noVNC :%d", name, novnc_port)
            except Exception as exc:
                logger.exception("chrome-pool: failed to start %s", name)
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
        logger.warning("chrome-pool: could not update .env: %s", exc)

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
        endpoint = base64.urlsafe_b64decode(endpoint_b64.encode()).decode()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid endpoint encoding")

    pool = get_pool()
    if endpoint not in pool.endpoints:
        raise HTTPException(status_code=404, detail=f"Endpoint {endpoint!r} not in pool")

    if body.mode is not None:
        if body.mode not in ("bridge", "cdp"):
            raise HTTPException(status_code=400, detail="mode must be 'bridge' or 'cdp'")
        pool.set_mode(endpoint, body.mode)

    clean_agent_url = body.agent_url.strip() if body.agent_url else None
    if body.agent_url is not None and isinstance(pool, LocalBrowserPool):
        pool.set_agent_url(endpoint, clean_agent_url or None)

    if body.agent_protocol is not None:
        if body.agent_protocol not in ("http", "ws"):
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
    if body.agent_url is not None:
        inst.agent_url = clean_agent_url or None
    if body.agent_protocol is not None:
        inst.agent_protocol = body.agent_protocol
    await db.commit()
    await db.refresh(inst)

    return ApiResponse.ok(BrowserInstanceRead.model_validate(inst))


@router.delete("/chrome-instances/{n}", response_model=ApiResponse[dict])
async def remove_chrome_instance(n: int) -> ApiResponse:
    """Stop and remove chrome-N (N >= 2). Instance 1 is managed by docker-compose."""
    if n < 2:
        raise HTTPException(status_code=400, detail="Instance 1 is managed by docker-compose")

    from backend.browser_pool import get_pool, LocalBrowserPool

    pool = get_pool()
    name = f"chrome-{n}"
    endpoint = f"http://{name}:19222"

    client = _docker_client()
    try:
        container = client.containers.get(name)
        container.remove(force=True)
        logger.info("chrome-pool: removed container %s", name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Container {name} not found: {exc}")

    if isinstance(pool, LocalBrowserPool):
        pool.remove_endpoint(endpoint)

    all_endpoints = ",".join(ep for ep in pool.endpoints if ep != endpoint)
    try:
        _update_env_file("AGENT_POOL_ENDPOINTS", all_endpoints)
    except Exception as exc:
        logger.warning("chrome-pool: could not update .env: %s", exc)

    return ApiResponse.ok({"removed": name, "total": len(pool.endpoints)})


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
