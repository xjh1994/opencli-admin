import asyncio
import logging
import os
import re
import socket

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.browser import BrowserBindingCreate, BrowserBindingRead
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

        # Persist mode to DB
        result = await db.execute(select(BrowserInstance).where(BrowserInstance.endpoint == new_endpoint))
        inst = result.scalar_one_or_none()
        if inst:
            inst.mode = mode
        else:
            inst = BrowserInstance(endpoint=new_endpoint, mode=mode, label="")
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
