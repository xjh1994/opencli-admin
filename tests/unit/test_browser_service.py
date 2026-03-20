"""Unit tests for backend/services/browser_service.py."""

import pytest

from backend.services import browser_service


@pytest.mark.asyncio
async def test_list_bindings_empty(db_session):
    """Returns empty list when no bindings exist."""
    result = await browser_service.list_bindings(db_session)
    assert result == []


@pytest.mark.asyncio
async def test_create_binding(db_session):
    """Creates a BrowserBinding and returns it."""
    binding = await browser_service.create_binding(
        db_session,
        browser_endpoint="http://chrome:9222",
        site="example.com",
        notes="test binding",
    )
    assert binding.id is not None
    assert binding.browser_endpoint == "http://chrome:9222"
    assert binding.site == "example.com"
    assert binding.notes == "test binding"


@pytest.mark.asyncio
async def test_create_binding_no_notes(db_session):
    """Creates a BrowserBinding with None notes."""
    binding = await browser_service.create_binding(
        db_session,
        browser_endpoint="http://chrome-2:9222",
        site="another.com",
    )
    assert binding.notes is None


@pytest.mark.asyncio
async def test_list_bindings_returns_all(db_session):
    """Returns all created bindings."""
    await browser_service.create_binding(db_session, "http://chrome:9222", "a.com")
    await browser_service.create_binding(db_session, "http://chrome-2:9222", "b.com")

    result = await browser_service.list_bindings(db_session)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_binding(db_session):
    """get_binding returns the binding for a given ID."""
    created = await browser_service.create_binding(db_session, "http://chrome:9222", "x.com")

    result = await browser_service.get_binding(db_session, created.id)
    assert result is not None
    assert result.id == created.id


@pytest.mark.asyncio
async def test_get_binding_not_found(db_session):
    """get_binding returns None for nonexistent ID."""
    result = await browser_service.get_binding(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_get_binding_by_site(db_session):
    """get_binding_by_site returns binding for the given site."""
    await browser_service.create_binding(db_session, "http://chrome:9222", "target.com")

    result = await browser_service.get_binding_by_site(db_session, "target.com")
    assert result is not None
    assert result.site == "target.com"


@pytest.mark.asyncio
async def test_get_binding_by_site_not_found(db_session):
    """get_binding_by_site returns None when site not found."""
    result = await browser_service.get_binding_by_site(db_session, "notfound.com")
    assert result is None


@pytest.mark.asyncio
async def test_delete_binding_success(db_session):
    """delete_binding returns True when binding exists and is deleted."""
    created = await browser_service.create_binding(db_session, "http://chrome:9222", "del.com")

    deleted = await browser_service.delete_binding(db_session, created.id)
    assert deleted is True

    check = await browser_service.get_binding(db_session, created.id)
    assert check is None


@pytest.mark.asyncio
async def test_delete_binding_not_found(db_session):
    """delete_binding returns False when binding doesn't exist."""
    deleted = await browser_service.delete_binding(db_session, "nonexistent-id")
    assert deleted is False
