from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ApiResponse, PaginationMeta
from backend.schemas.record import CollectedRecordRead
from backend.services import record_service

router = APIRouter(prefix="/records", tags=["records"])


class BatchDeleteRequest(BaseModel):
    ids: list[str]


@router.get("", response_model=ApiResponse[list[CollectedRecordRead]])
async def list_records(
    source_id: Optional[str] = None,
    task_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    records, total = await record_service.list_records(
        db,
        source_id=source_id,
        task_id=task_id,
        status=status,
        search=search,
        page=page,
        limit=limit,
    )
    return ApiResponse.ok(
        data=[CollectedRecordRead.model_validate(r) for r in records],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=max(1, -(-total // limit))),
    )


@router.get("/{record_id}", response_model=ApiResponse[CollectedRecordRead])
async def get_record(
    record_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    record = await record_service.get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return ApiResponse.ok(CollectedRecordRead.model_validate(record))


@router.delete("/{record_id}", response_model=ApiResponse[None])
async def delete_record(
    record_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    deleted = await record_service.delete_records(db, [record_id])
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return ApiResponse.ok(None)


@router.post("/batch-delete", response_model=ApiResponse[dict])
async def batch_delete_records(
    body: BatchDeleteRequest, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    if not body.ids:
        return ApiResponse.ok({"deleted": 0})
    deleted = await record_service.delete_records(db, body.ids)
    return ApiResponse.ok({"deleted": deleted})


@router.delete("", response_model=ApiResponse[dict])
async def clear_all_records(
    source_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    deleted = await record_service.delete_all_records(db, source_id=source_id)
    return ApiResponse.ok({"deleted": deleted})
