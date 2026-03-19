"""CDP browser endpoint pool.

Distributes opencli collection tasks across multiple Chrome instances so tasks
can run concurrently without competing for a single browser.

Two implementations:
  LocalBrowserPool  — asyncio.Queue, for TASK_EXECUTOR=local (in-process).
  RedisBrowserPool  — Redis BLPOP/RPUSH, for TASK_EXECUTOR=celery (distributed
                      workers across processes / machines).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class LocalBrowserPool:
    """In-process pool backed by asyncio.Queue."""

    def __init__(self, endpoints: list[str]) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        for ep in endpoints:
            self._queue.put_nowait(ep)
        self._total = len(endpoints)
        logger.info(
            "BrowserPool (local): %d Chrome instance(s): %s",
            self._total,
            endpoints,
        )

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[str]:
        endpoint = await self._queue.get()
        logger.debug(
            "Chrome acquired: %s (available: %d/%d)",
            endpoint,
            self._queue.qsize(),
            self._total,
        )
        try:
            yield endpoint
        finally:
            self._queue.put_nowait(endpoint)
            logger.debug("Chrome released: %s", endpoint)

    @property
    def total(self) -> int:
        return self._total

    @property
    def available(self) -> int:
        return self._queue.qsize()


class RedisBrowserPool:
    """Distributed pool backed by a Redis list (BLPOP/RPUSH).

    Safe across multiple Celery worker processes and machines.
    The pool list is initialised once (checked via key existence) so that
    multiple API/worker replicas don't double-push endpoints.
    """

    _POOL_KEY = "browser_pool:endpoints"
    _LOCK_KEY = "browser_pool:initialized"

    def __init__(self, endpoints: list[str], redis_url: str) -> None:
        self._endpoints = endpoints
        self._redis_url = redis_url
        self._total = len(endpoints)

    def _client(self):
        import redis.asyncio as aioredis  # type: ignore[import]
        return aioredis.from_url(self._redis_url, decode_responses=True)

    async def initialize(self) -> None:
        """Populate the Redis pool list (idempotent — uses SET NX lock)."""
        async with self._client() as r:
            acquired = await r.set(self._LOCK_KEY, "1", nx=True, ex=3600)
            if acquired:
                await r.delete(self._POOL_KEY)
                if self._endpoints:
                    await r.rpush(self._POOL_KEY, *self._endpoints)
                logger.info(
                    "BrowserPool (Redis): %d Chrome instance(s) pushed to %s",
                    self._total,
                    self._POOL_KEY,
                )
            else:
                logger.info("BrowserPool (Redis): pool already initialized by another replica")

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[str]:
        async with self._client() as r:
            result = await r.blpop(self._POOL_KEY, timeout=300)
        if result is None:
            raise TimeoutError(
                "No Chrome instance became available within 5 minutes. "
                "Check that chrome containers are running."
            )
        _, endpoint = result
        logger.debug("Chrome acquired (Redis): %s", endpoint)
        try:
            yield endpoint
        finally:
            async with self._client() as r:
                await r.rpush(self._POOL_KEY, endpoint)
            logger.debug("Chrome released (Redis): %s", endpoint)

    @property
    def total(self) -> int:
        return self._total

    @property
    def available(self) -> int:
        return -1  # unknown without a sync Redis call; not needed for operations


# ── Module-level singleton ────────────────────────────────────────────────────

_pool: LocalBrowserPool | RedisBrowserPool | None = None


def init_pool(
    endpoints: list[str],
    use_redis: bool = False,
    redis_url: str = "",
) -> LocalBrowserPool | RedisBrowserPool:
    global _pool
    if use_redis and redis_url:
        _pool = RedisBrowserPool(endpoints, redis_url)
    else:
        _pool = LocalBrowserPool(endpoints)
    return _pool


async def ensure_ready() -> None:
    """Async post-init step (populates Redis list if applicable)."""
    if isinstance(_pool, RedisBrowserPool):
        await _pool.initialize()


def get_pool() -> LocalBrowserPool | RedisBrowserPool:
    if _pool is None:
        raise RuntimeError("BrowserPool not initialized — call init_pool() first")
    return _pool
