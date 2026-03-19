from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.browser import BrowserBindingCreate, BrowserBindingRead
from backend.schemas.common import ApiResponse
from backend.services import browser_service

router = APIRouter(prefix="/browsers", tags=["browsers"])


@router.get("/bindings", response_model=ApiResponse[list[BrowserBindingRead]])
async def list_bindings(db: AsyncSession = Depends(get_db)) -> ApiResponse:
    bindings = await browser_service.list_bindings(db)
    return ApiResponse.ok([BrowserBindingRead.model_validate(b) for b in bindings])


@router.post("/bindings", response_model=ApiResponse[BrowserBindingRead])
async def create_binding(
    body: BrowserBindingCreate, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    existing = await browser_service.get_binding_by_site(db, body.site)
    if existing:
        raise HTTPException(status_code=409, detail=f"Site '{body.site}' is already bound")
    binding = await browser_service.create_binding(
        db, body.browser_endpoint, body.site, body.notes
    )
    await db.commit()
    return ApiResponse.ok(BrowserBindingRead.model_validate(binding))


@router.delete("/bindings/{binding_id}", response_model=ApiResponse[None])
async def delete_binding(
    binding_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    deleted = await browser_service.delete_binding(db, binding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Binding not found")
    await db.commit()
    return ApiResponse.ok(None)
