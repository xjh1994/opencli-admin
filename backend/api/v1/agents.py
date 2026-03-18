"""CRUD endpoints for AI agents."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.agent import AIAgent
from backend.schemas.agent import AIAgentCreate, AIAgentRead, AIAgentUpdate
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=ApiResponse[list[AIAgentRead]])
async def list_agents(
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(AIAgent).order_by(AIAgent.created_at.desc())
    if enabled is not None:
        query = query.where(AIAgent.enabled == enabled)
    result = await db.execute(query)
    agents = result.scalars().all()
    return ApiResponse.ok(list(agents))


@router.post("", response_model=ApiResponse[AIAgentRead], status_code=201)
async def create_agent(body: AIAgentCreate, db: AsyncSession = Depends(get_db)):
    agent = AIAgent(**body.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return ApiResponse.ok(agent)


@router.get("/{agent_id}", response_model=ApiResponse[AIAgentRead])
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIAgent).where(AIAgent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse.ok(agent)


@router.patch("/{agent_id}", response_model=ApiResponse[AIAgentRead])
async def update_agent(
    agent_id: str, body: AIAgentUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(AIAgent).where(AIAgent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return ApiResponse.ok(agent)


@router.delete("/{agent_id}", response_model=ApiResponse[None])
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIAgent).where(AIAgent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
    return ApiResponse.ok(None)
