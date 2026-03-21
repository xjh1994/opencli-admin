import re
from urllib.parse import urlparse
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.browser_pool import get_pool

router = APIRouter(prefix="/workers", tags=["workers"])


def _inspect_workers() -> tuple[dict, dict]:
    from backend.worker.celery_app import celery_app
    inspect = celery_app.control.inspect(timeout=3)
    return inspect.stats() or {}, inspect.active() or {}


@router.get("", response_model=ApiResponse[list[dict]])
async def list_workers(db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """Return live Celery worker nodes derived from broker inspect."""
    try:
        stats, active = _inspect_workers()
        workers = []
        for worker_id, info in stats.items():
            active_tasks = len(active.get(worker_id, []))
            workers.append({
                "id": worker_id,
                "worker_id": worker_id,
                "hostname": info.get("hostname", worker_id),
                "status": "online",
                "active_tasks": active_tasks,
                "last_heartbeat": None,
                "concurrency": info.get("pool", {}).get("max-concurrency"),
                "celery_version": info.get("versions", {}).get("celery"),
            })
        return ApiResponse.ok(workers)
    except Exception:
        return ApiResponse.ok([])


def _novnc_port(cdp_url: str, base_port: int) -> int:
    """Derive the noVNC web-UI port from a CDP endpoint URL.

    Naming convention: agent → 1, agent-2 → 2, agent-N → N.
    noVNC port = base_port + (N - 1).
    """
    hostname = urlparse(cdp_url).hostname or ""
    m = re.match(r"^agent(?:-(\d+))?$", hostname)
    n = int(m.group(1)) if (m and m.group(1)) else 1
    return base_port + (n - 1)


def _container_status(hostname: str) -> str:
    """Return Docker container status string, or 'unknown' if unavailable."""
    try:
        import docker  # type: ignore[import]
        client = docker.from_env()
        return client.containers.get(hostname).status
    except Exception:
        return "unknown"


@router.get("/chrome-pool", response_model=ApiResponse[dict])
async def chrome_pool_status() -> ApiResponse:
    """Return agent pool status and available endpoints."""
    pool = get_pool()
    base_port = get_settings().novnc_base_port
    from backend.browser_pool import LocalBrowserPool
    endpoints = [
        {
            "url": ep,
            "available": pool.available_for(ep),
            "novnc_port": _novnc_port(ep, base_port),
            "container_status": _container_status(urlparse(ep).hostname or ""),
            "mode": pool.get_mode(ep),
            "agent_url": pool.get_agent_url(ep) if isinstance(pool, LocalBrowserPool) else None,
            "agent_protocol": pool.get_agent_protocol(ep) if isinstance(pool, LocalBrowserPool) else None,
        }
        for ep in pool.endpoints
    ]
    return ApiResponse.ok({
        "endpoints": endpoints,
        "total": pool.total,
        "available": pool.available,
    })


class EndpointModeUpdate(BaseModel):
    mode: Literal["bridge", "cdp"]


@router.patch("/chrome-pool/{endpoint_b64}/mode", response_model=ApiResponse[dict])
async def update_endpoint_mode(
    endpoint_b64: str,
    body: EndpointModeUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Update the connection mode (bridge/cdp) for an agent pool endpoint."""
    import base64
    from backend.models.browser import BrowserInstance

    try:
        padded = endpoint_b64 + "=" * (-len(endpoint_b64) % 4)
        endpoint = base64.urlsafe_b64decode(padded.encode()).decode()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid endpoint encoding")

    pool = get_pool()
    if endpoint not in pool.endpoints:
        raise HTTPException(status_code=404, detail=f"Endpoint {endpoint!r} not in pool")

    # Update in-memory pool
    pool.set_mode(endpoint, body.mode)

    # Persist to DB
    result = await db.execute(select(BrowserInstance).where(BrowserInstance.endpoint == endpoint))
    inst = result.scalar_one_or_none()
    if inst:
        inst.mode = body.mode
    else:
        inst = BrowserInstance(endpoint=endpoint, mode=body.mode, label="")
        db.add(inst)
    await db.commit()

    return ApiResponse.ok({"endpoint": endpoint, "mode": body.mode})


@router.get("/celery-stats", response_model=ApiResponse[dict])
async def celery_stats() -> ApiResponse:
    """Query live Celery worker stats via inspect."""
    try:
        stats, active = _inspect_workers()
        return ApiResponse.ok({"stats": stats, "active": active})
    except Exception as exc:
        return ApiResponse.ok({"error": str(exc), "stats": {}, "active": {}})
