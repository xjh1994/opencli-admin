"""Unit tests for LocalBrowserPool from backend/browser_pool.py."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.browser_pool import LocalBrowserPool


@pytest.fixture
def pool():
    return LocalBrowserPool(["http://chrome:9222", "http://chrome-2:9222"])


@pytest.fixture
def empty_pool():
    return LocalBrowserPool([])


# ── properties ────────────────────────────────────────────────────────────────

def test_total_equals_endpoint_count(pool):
    assert pool.total == 2


def test_endpoints_returns_all(pool):
    endpoints = pool.endpoints
    assert "http://chrome:9222" in endpoints
    assert "http://chrome-2:9222" in endpoints
    assert len(endpoints) == 2


def test_available_initially_equals_total(pool):
    assert pool.available == 2


def test_available_for_all_endpoints_initially(pool):
    assert pool.available_for("http://chrome:9222") is True
    assert pool.available_for("http://chrome-2:9222") is True


def test_available_for_unknown_endpoint(pool):
    assert pool.available_for("http://unknown:9222") is False


# ── mode management ────────────────────────────────────────────────────────────

def test_default_mode_is_bridge(pool):
    assert pool.get_mode("http://chrome:9222") == "bridge"


def test_set_mode_updates_mode(pool):
    pool.set_mode("http://chrome:9222", "cdp")
    assert pool.get_mode("http://chrome:9222") == "cdp"


def test_get_mode_unknown_endpoint_returns_bridge(pool):
    assert pool.get_mode("http://unknown:9222") == "bridge"


# ── agent_url management ───────────────────────────────────────────────────────

def test_default_agent_url_is_none(pool):
    assert pool.get_agent_url("http://chrome:9222") is None


def test_set_agent_url(pool):
    pool.set_agent_url("http://chrome:9222", "http://agent:8080")
    assert pool.get_agent_url("http://chrome:9222") == "http://agent:8080"


def test_default_agent_protocol_is_none(pool):
    assert pool.get_agent_protocol("http://chrome:9222") is None


def test_set_agent_protocol(pool):
    pool.set_agent_protocol("http://chrome:9222", "http")
    assert pool.get_agent_protocol("http://chrome:9222") == "http"


# ── add/remove endpoints ───────────────────────────────────────────────────────

def test_add_endpoint_increases_total(pool):
    pool.add_endpoint("http://chrome-3:9222")
    assert pool.total == 3
    assert "http://chrome-3:9222" in pool.endpoints


def test_add_endpoint_already_exists_no_duplicate(pool):
    pool.add_endpoint("http://chrome:9222")
    assert pool.total == 2  # no change


def test_remove_endpoint_decreases_total(pool):
    pool.remove_endpoint("http://chrome:9222")
    assert pool.total == 1
    assert "http://chrome:9222" not in pool.endpoints


def test_remove_endpoint_nonexistent_no_error(pool):
    pool.remove_endpoint("http://nonexistent:9222")
    assert pool.total == 2  # no change


# ── acquire / release via context manager ─────────────────────────────────────

@pytest.mark.asyncio
async def test_acquire_specific_endpoint(pool):
    """Acquiring a specific endpoint yields that endpoint URL."""
    async with pool.acquire("http://chrome:9222") as ep:
        assert ep == "http://chrome:9222"
        # While acquired, that slot is not available
        assert pool.available_for("http://chrome:9222") is False


@pytest.mark.asyncio
async def test_acquire_any_endpoint(pool):
    """Acquiring any endpoint returns one of the available endpoints."""
    async with pool.acquire() as ep:
        assert ep in ["http://chrome:9222", "http://chrome-2:9222"]


@pytest.mark.asyncio
async def test_acquire_releases_on_exit(pool):
    """Slot is returned to the pool after the context manager exits."""
    async with pool.acquire("http://chrome:9222") as ep:
        assert ep == "http://chrome:9222"

    # After exit, slot should be available again
    assert pool.available_for("http://chrome:9222") is True


# ── empty pool ────────────────────────────────────────────────────────────────

def test_empty_pool_total_is_zero(empty_pool):
    assert empty_pool.total == 0


def test_empty_pool_available_is_zero(empty_pool):
    assert empty_pool.available == 0


def test_empty_pool_endpoints_is_empty(empty_pool):
    assert empty_pool.endpoints == []


# ── init_pool / get_pool ───────────────────────────────────────────────────────

def test_init_pool_local(monkeypatch):
    """init_pool with use_redis=False creates a LocalBrowserPool."""
    from backend import browser_pool

    browser_pool.init_pool(["http://chrome:9222"], use_redis=False)
    pool = browser_pool.get_pool()
    assert isinstance(pool, LocalBrowserPool)
    assert pool.total == 1


def test_get_pool_raises_when_not_initialized():
    """get_pool raises RuntimeError when init_pool hasn't been called."""
    from backend import browser_pool

    browser_pool._pool = None
    with pytest.raises(RuntimeError, match="not initialized"):
        browser_pool.get_pool()


@pytest.mark.asyncio
async def test_ensure_ready_local_pool_noop():
    """ensure_ready does nothing for LocalBrowserPool."""
    from backend import browser_pool

    browser_pool.init_pool(["http://chrome:9222"], use_redis=False)
    # Should not raise
    await browser_pool.ensure_ready()


# ── LocalBrowserPool: _acquire_any concurrent acquisition ─────────────────────

@pytest.mark.asyncio
async def test_acquire_any_concurrent_gets_endpoints():
    """Two concurrent unrouted acquires each get a Chrome endpoint."""
    pool = LocalBrowserPool(["http://chrome:9222", "http://chrome-2:9222"])
    acquired = []

    async def grab():
        async with pool.acquire() as ep:
            acquired.append(ep)
            await asyncio.sleep(0.01)  # hold briefly

    await asyncio.gather(grab(), grab())
    # Both acquisitions should have succeeded
    assert len(acquired) == 2
    # Each acquired endpoint should be valid
    for ep in acquired:
        assert ep in ["http://chrome:9222", "http://chrome-2:9222"]


# ── RedisBrowserPool properties ────────────────────────────────────────────────

def test_redis_pool_properties():
    """RedisBrowserPool exposes the correct properties."""
    from backend.browser_pool import RedisBrowserPool

    pool = RedisBrowserPool(["http://chrome:9222", "http://chrome-2:9222"], "redis://localhost:6379")
    assert pool.total == 2
    assert pool.available == -1  # unknown
    assert "http://chrome:9222" in pool.endpoints
    assert pool.available_for("http://chrome:9222") is True
    assert pool.available_for("http://nonexistent:9222") is False


def test_redis_pool_ep_key():
    """_ep_key generates safe Redis keys from endpoint URLs."""
    from backend.browser_pool import RedisBrowserPool

    key = RedisBrowserPool._ep_key("http://chrome:9222")
    assert "://" not in key
    assert key.startswith("browser_pool:ep:")


# ── LocalBrowserPool: acquire fallback for unknown endpoint ──────────────────

@pytest.mark.asyncio
async def test_acquire_unknown_endpoint_falls_back_to_any():
    """Requesting an endpoint not in pool falls back to any available instance."""
    p = LocalBrowserPool(["http://chrome:9222"])
    async with p.acquire("http://not-in-pool:9222") as ep:
        assert ep == "http://chrome:9222"


# ── init_pool with Redis ──────────────────────────────────────────────────────

def test_init_pool_redis(monkeypatch):
    """init_pool with use_redis=True and redis_url creates a RedisBrowserPool."""
    from backend import browser_pool
    from backend.browser_pool import RedisBrowserPool

    pool = browser_pool.init_pool(
        ["http://chrome:9222"],
        use_redis=True,
        redis_url="redis://localhost:6379",
    )
    assert isinstance(pool, RedisBrowserPool)
    assert pool.total == 1


@pytest.mark.asyncio
async def test_ensure_ready_redis_pool_calls_initialize():
    """ensure_ready calls initialize() on RedisBrowserPool."""
    from backend import browser_pool
    from backend.browser_pool import RedisBrowserPool

    redis_pool = RedisBrowserPool(["http://chrome:9222"], "redis://localhost:6379")
    redis_pool.initialize = AsyncMock()
    browser_pool._pool = redis_pool

    await browser_pool.ensure_ready()

    redis_pool.initialize.assert_awaited_once()


# ── RedisBrowserPool._client ─────────────────────────────────────────────────

def test_redis_pool_client_returns_redis_client():
    """_client() returns an aioredis client from the configured URL."""
    from backend.browser_pool import RedisBrowserPool
    from unittest.mock import MagicMock

    mock_redis_client = MagicMock()
    with patch("redis.asyncio.from_url", return_value=mock_redis_client):
        pool = RedisBrowserPool(["http://chrome:9222"], "redis://localhost:6379")
        client = pool._client()

    assert client is mock_redis_client


# ── RedisBrowserPool.initialize ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_redis_pool_initialize():
    """initialize() populates the pool keys in Redis."""
    from backend.browser_pool import RedisBrowserPool
    from unittest.mock import AsyncMock, MagicMock

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()
    mock_redis.rpush = AsyncMock()
    mock_redis_cm = AsyncMock()
    mock_redis_cm.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis_cm.__aexit__ = AsyncMock(return_value=False)

    pool = RedisBrowserPool(["http://chrome:9222"], "redis://localhost:6379")

    with patch.object(pool, "_client", return_value=mock_redis_cm):
        await pool.initialize()

    mock_redis.rpush.assert_called()


@pytest.mark.asyncio
async def test_redis_pool_initialize_already_initialized():
    """initialize() is a no-op if pool already initialized (lock not acquired)."""
    from backend.browser_pool import RedisBrowserPool

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)  # lock not acquired
    mock_redis_cm = AsyncMock()
    mock_redis_cm.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis_cm.__aexit__ = AsyncMock(return_value=False)

    pool = RedisBrowserPool(["http://chrome:9222"], "redis://localhost:6379")

    with patch.object(pool, "_client", return_value=mock_redis_cm):
        await pool.initialize()

    mock_redis.rpush.assert_not_called()


# ── RedisBrowserPool.acquire ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_redis_pool_acquire_any():
    """acquire() without endpoint blpops from the shared pool key."""
    from backend.browser_pool import RedisBrowserPool

    ep = "http://chrome:9222"
    mock_redis = AsyncMock()
    mock_redis.blpop = AsyncMock(return_value=("browser_pool:available", ep))
    mock_redis.rpush = AsyncMock()
    mock_redis_cm = AsyncMock()
    mock_redis_cm.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis_cm.__aexit__ = AsyncMock(return_value=False)

    pool = RedisBrowserPool([ep], "redis://localhost:6379")

    with patch.object(pool, "_client", return_value=mock_redis_cm):
        async with pool.acquire() as acquired_ep:
            assert acquired_ep == ep


@pytest.mark.asyncio
async def test_redis_pool_acquire_routed():
    """acquire(endpoint) blpops from the per-endpoint key."""
    from backend.browser_pool import RedisBrowserPool

    ep = "http://chrome:9222"
    mock_redis = AsyncMock()
    mock_redis.blpop = AsyncMock(return_value=(f"browser_pool:ep:{ep}", ep))
    mock_redis.rpush = AsyncMock()
    mock_redis_cm = AsyncMock()
    mock_redis_cm.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis_cm.__aexit__ = AsyncMock(return_value=False)

    pool = RedisBrowserPool([ep], "redis://localhost:6379")

    with patch.object(pool, "_client", return_value=mock_redis_cm):
        async with pool.acquire(ep) as acquired_ep:
            assert acquired_ep == ep


@pytest.mark.asyncio
async def test_redis_pool_acquire_timeout():
    """acquire() raises TimeoutError when blpop returns None."""
    from backend.browser_pool import RedisBrowserPool

    mock_redis = AsyncMock()
    mock_redis.blpop = AsyncMock(return_value=None)
    mock_redis_cm = AsyncMock()
    mock_redis_cm.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis_cm.__aexit__ = AsyncMock(return_value=False)

    pool = RedisBrowserPool(["http://chrome:9222"], "redis://localhost:6379")

    with patch.object(pool, "_client", return_value=mock_redis_cm):
        with pytest.raises(TimeoutError):
            async with pool.acquire():
                pass
