"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import os

from backend.api.v1 import v1_router
from backend.config import get_settings
from backend.database import run_migrations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Docker: migrations already run by entrypoint.sh (RUN_MIGRATIONS=true).
    # Native shell: run them here since there is no entrypoint wrapper.
    if os.environ.get("RUN_MIGRATIONS") != "true":
        await run_migrations()
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
