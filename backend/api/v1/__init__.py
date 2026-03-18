"""API v1 router package."""

from fastapi import APIRouter

from backend.api.v1 import (
    agents,
    dashboard,
    notifications,
    records,
    schedules,
    sources,
    tasks,
    webhooks,
    workers,
)

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(agents.router)
v1_router.include_router(sources.router)
v1_router.include_router(tasks.router)
v1_router.include_router(records.router)
v1_router.include_router(schedules.router)
v1_router.include_router(webhooks.router)
v1_router.include_router(notifications.router)
v1_router.include_router(workers.router)
v1_router.include_router(dashboard.router)
