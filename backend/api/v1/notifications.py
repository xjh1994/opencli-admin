from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.notification import NotificationLog, NotificationRule
from backend.schemas.common import ApiResponse, PaginationMeta
from backend.schemas.notification import (
    NotificationLogRead,
    NotificationRuleCreate,
    NotificationRuleRead,
    NotificationRuleUpdate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/rules", response_model=ApiResponse[list[NotificationRuleRead]])
async def list_rules(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    total = (await db.execute(select(func.count()).select_from(NotificationRule))).scalar_one()
    result = await db.execute(
        select(NotificationRule).offset((page - 1) * limit).limit(limit)
    )
    rules = result.scalars().all()
    return ApiResponse.ok(
        data=[NotificationRuleRead.model_validate(r) for r in rules],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=max(1, -(-total // limit))),
    )


@router.post("/rules", response_model=ApiResponse[NotificationRuleRead], status_code=201)
async def create_rule(
    body: NotificationRuleCreate, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    rule = NotificationRule(**body.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return ApiResponse.ok(NotificationRuleRead.model_validate(rule))


@router.get("/rules/{rule_id}", response_model=ApiResponse[NotificationRuleRead])
async def get_rule(rule_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    result = await db.execute(select(NotificationRule).where(NotificationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return ApiResponse.ok(NotificationRuleRead.model_validate(rule))


@router.patch("/rules/{rule_id}", response_model=ApiResponse[NotificationRuleRead])
async def update_rule(
    rule_id: str, body: NotificationRuleUpdate, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    result = await db.execute(select(NotificationRule).where(NotificationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    await db.flush()
    await db.refresh(rule)
    return ApiResponse.ok(NotificationRuleRead.model_validate(rule))


@router.delete("/rules/{rule_id}", response_model=ApiResponse[None])
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    result = await db.execute(select(NotificationRule).where(NotificationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    return ApiResponse.ok(None)


@router.get("/logs", response_model=ApiResponse[list[NotificationLogRead]])
async def list_logs(
    rule_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    query = select(NotificationLog).order_by(NotificationLog.created_at.desc())
    count_query = select(func.count()).select_from(NotificationLog)
    if rule_id:
        query = query.where(NotificationLog.rule_id == rule_id)
        count_query = count_query.where(NotificationLog.rule_id == rule_id)
    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    logs = result.scalars().all()
    return ApiResponse.ok(
        data=[NotificationLogRead.model_validate(log) for log in logs],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=max(1, -(-total // limit))),
    )
