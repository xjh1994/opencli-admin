"""Webhook ingress: external systems trigger collection via HTTP."""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services import source_service, task_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)
settings = get_settings()


def _verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    """Verify X-Signature-256: sha256=<hex> header."""
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/{source_id}", response_model=ApiResponse[dict], status_code=202)
async def webhook_trigger(
    source_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    source = await source_service.get_source(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.enabled:
        raise HTTPException(status_code=400, detail="Source is disabled")

    # HMAC verification if webhook_secret configured per-source
    webhook_secret = source.channel_config.get("webhook_secret", settings.webhook_secret)
    if webhook_secret:
        signature = request.headers.get("X-Signature-256", "")
        body = await request.body()
        if not _verify_hmac(body, signature, webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        payload = {}

    task = await task_service.create_task(
        db,
        source_id=source_id,
        trigger_type="webhook",
        parameters=payload,
        priority=5,
    )

    from backend.executor import get_executor
    result = await get_executor().dispatch_collection(task.id, payload)

    return ApiResponse.ok(result)
