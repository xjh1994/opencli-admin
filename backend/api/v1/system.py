"""System configuration endpoint."""

import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import get_settings
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/system", tags=["system"])

_ENV_PATH = "/app/.env"


def _update_env_file(key: str, value: str) -> None:
    try:
        with open(_ENV_PATH) as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    new_line = f"{key}={value}"
    pattern = rf"^{re.escape(key)}=.*$"
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + f"\n{new_line}\n"
    with open(_ENV_PATH, "w") as f:
        f.write(content)


class ConfigPatch(BaseModel):
    collection_mode: str | None = None


@router.get("/config", response_model=ApiResponse[dict])
async def get_config() -> ApiResponse:
    s = get_settings()
    return ApiResponse.ok(
        {
            "collection_mode": s.collection_mode,
            "task_executor": s.task_executor,
        }
    )


@router.patch("/config", response_model=ApiResponse[dict])
async def update_config(body: ConfigPatch) -> ApiResponse:
    if body.collection_mode is not None:
        if body.collection_mode not in ("local", "agent"):
            raise HTTPException(
                status_code=400, detail="collection_mode must be 'local' or 'agent'"
            )
        _update_env_file("COLLECTION_MODE", body.collection_mode)
        # Also update the process env var so pydantic-settings picks up the new value
        # (env vars take priority over .env file in pydantic-settings v2)
        os.environ["COLLECTION_MODE"] = body.collection_mode
        get_settings.cache_clear()

    s = get_settings()
    return ApiResponse.ok(
        {
            "collection_mode": s.collection_mode,
            "task_executor": s.task_executor,
        }
    )
