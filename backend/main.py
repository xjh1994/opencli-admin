"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.v1 import v1_router
from backend.config import get_settings
from backend.database import run_migrations

def _configure_logging() -> None:
    """Restore backend.* logging after uvicorn's dictConfig disables pre-existing loggers.

    uvicorn calls logging.config.dictConfig(LOGGING_CONFIG) with disable_existing_loggers=True,
    which disables all loggers that were created before the config ran (i.e. all loggers
    imported at module level). Also, alembic resets the root logger level to WARNING.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Re-enable all backend.* loggers that uvicorn's dictConfig disabled
    for name, lgr in logging.root.manager.loggerDict.items():
        if name.startswith("backend") and isinstance(lgr, logging.Logger):
            lgr.disabled = False
            lgr.setLevel(logging.INFO)


_configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


def _read_chrome_endpoints() -> list[str]:
    """Read CHROME_POOL_ENDPOINTS from the .env file directly.

    `docker restart` reuses the env vars baked in at container creation time,
    so the env var value is stale after the chrome-pool API updates .env.
    Reading the file directly always gets the current value.
    """
    try:
        from dotenv import dotenv_values
        env = dotenv_values("/app/.env")
        raw = env.get("CHROME_POOL_ENDPOINTS", "").strip()
        if raw:
            return [ep.strip() for ep in raw.split(",") if ep.strip()]
    except Exception:
        pass
    return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    # Re-apply logging config: alembic resets root logger level to WARNING during migrations
    # and uvicorn's dictConfig disables pre-existing loggers
    _configure_logging()

    # Initialise Chrome browser pool.
    # Read CHROME_POOL_ENDPOINTS directly from the .env file so that updates
    # written by the chrome-pool API survive a plain `docker restart` — docker
    # restart reuses the env vars injected at container creation time, so the
    # pydantic-settings value (which comes from those env vars) would be stale.
    from backend import browser_pool
    endpoints = _read_chrome_endpoints() or settings.cdp_endpoints
    browser_pool.init_pool(
        endpoints=endpoints,
        use_redis=settings.task_executor == "celery",
        redis_url=settings.redis_url,
    )
    await browser_pool.ensure_ready()

    # Sync browser instance modes from DB into pool memory
    from backend.database import AsyncSessionLocal
    from backend.models.browser import BrowserInstance
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BrowserInstance))
        for inst in result.scalars().all():
            if inst.endpoint in [ep for ep in browser_pool.get_pool().endpoints]:
                browser_pool.get_pool().set_mode(inst.endpoint, inst.mode)

    # Mark stale pending/running tasks as failed (lost on previous restart)
    from backend.models.task import CollectionTask
    from sqlalchemy import update
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(CollectionTask)
            .where(CollectionTask.status.in_(["pending", "running", "ai_processing"]))
            .values(status="failed", error_message="Task lost on server restart")
        )
        await session.commit()
    logger.info("Recovered stale tasks on startup")

    if settings.task_executor == "local":
        from backend.scheduler import start_scheduler
        start_scheduler()
    logger.info(
        "OpenCLI Admin started (env=%s, executor=%s)",
        settings.app_env,
        settings.task_executor,
    )
    yield
    # Shutdown
    if settings.task_executor == "local":
        from backend.scheduler import stop_scheduler
        stop_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenCLI Admin",
        description="Multi-channel data collection management system",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"},
        )

    # Routes
    app.include_router(v1_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": "0.1.0", "task_executor": settings.task_executor}

    return app


app = create_app()
