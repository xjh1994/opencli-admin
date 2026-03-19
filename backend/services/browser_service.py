from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.browser import BrowserBinding


async def list_bindings(session: AsyncSession) -> list[BrowserBinding]:
    result = await session.execute(select(BrowserBinding).order_by(BrowserBinding.site))
    return list(result.scalars().all())


async def get_binding(session: AsyncSession, binding_id: str) -> Optional[BrowserBinding]:
    return await session.get(BrowserBinding, binding_id)


async def get_binding_by_site(session: AsyncSession, site: str) -> Optional[BrowserBinding]:
    result = await session.execute(
        select(BrowserBinding).where(BrowserBinding.site == site)
    )
    return result.scalar_one_or_none()


async def create_binding(
    session: AsyncSession, browser_endpoint: str, site: str, notes: str | None = None
) -> BrowserBinding:
    binding = BrowserBinding(browser_endpoint=browser_endpoint, site=site, notes=notes)
    session.add(binding)
    await session.flush()
    await session.refresh(binding)
    return binding


async def delete_binding(session: AsyncSession, binding_id: str) -> bool:
    result = await session.execute(
        delete(BrowserBinding).where(BrowserBinding.id == binding_id)
    )
    return result.rowcount > 0
