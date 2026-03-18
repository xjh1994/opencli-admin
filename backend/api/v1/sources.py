from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ApiResponse, PaginationMeta
from backend.schemas.source import DataSourceCreate, DataSourceDetail, DataSourceRead, DataSourceUpdate
from backend.services import source_service

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=ApiResponse[list[DataSourceRead]])
async def list_sources(
    enabled: Optional[bool] = None,
    channel_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    sources, total = await source_service.list_sources(
        db, enabled=enabled, channel_type=channel_type, page=page, limit=limit
    )
    return ApiResponse.ok(
        data=[DataSourceRead.model_validate(s) for s in sources],
        meta=PaginationMeta(
            total=total, page=page, limit=limit, pages=max(1, -(-total // limit))
        ),
    )


@router.post("", response_model=ApiResponse[DataSourceRead], status_code=201)
async def create_source(
    body: DataSourceCreate, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    source = await source_service.create_source(db, body)
    return ApiResponse.ok(DataSourceRead.model_validate(source))


@router.get("/{source_id}", response_model=ApiResponse[DataSourceDetail])
async def get_source(
    source_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    source = await source_service.get_source(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return ApiResponse.ok(DataSourceDetail.model_validate(source))


@router.patch("/{source_id}", response_model=ApiResponse[DataSourceRead])
async def update_source(
    source_id: str, body: DataSourceUpdate, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    source = await source_service.get_source(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    updated = await source_service.update_source(db, source, body)
    return ApiResponse.ok(DataSourceRead.model_validate(updated))


@router.delete("/{source_id}", response_model=ApiResponse[None])
async def delete_source(
    source_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    source = await source_service.get_source(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await source_service.delete_source(db, source)
    return ApiResponse.ok(None)


@router.post("/{source_id}/test", response_model=ApiResponse[dict])
async def test_source(
    source_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    source = await source_service.get_source(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    ok, errors = await source_service.test_source_connectivity(source)
    return ApiResponse.ok({"connected": ok, "errors": errors})
