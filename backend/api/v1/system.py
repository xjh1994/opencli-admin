"""System configuration endpoint."""

import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import get_settings
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/system", tags=["system"])

def _resolve_env_path() -> str:
    if explicit := os.environ.get("ENV_FILE_PATH"):
        return explicit
    for candidate in [
        "/app/.env",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"),
    ]:
        if os.path.exists(candidate):
            return candidate
    # Fallback: project root .env (will be created if missing)
    return os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")


def _update_env_file(key: str, value: str) -> None:
    path = _resolve_env_path()
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
