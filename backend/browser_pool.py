"""CDP browser endpoint pool.

Distributes opencli collection tasks across multiple Chrome instances so tasks
can run concurrently without competing for a single browser.

Two implementations:
  LocalBrowserPool  — per-endpoint asyncio.Queue slots, for TASK_EXECUTOR=local.
  RedisBrowserPool  — Redis BLPOP/RPUSH, for TASK_EXECUTOR=celery (distributed
                      workers across processes / machines).

Routing:
  acquire(endpoint=None)         — any available instance (round-robin / first-free)
  acquire(endpoint="http://...")  — wait specifically for that Chrome instance

Use routing to pin certain data sources to a Chrome instance that is logged into
a specific site (e.g. only chrome-2 is logged into Twitter).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class LocalBrowserPool:
    """In-process pool backed by per-endpoint asyncio.Queue slots.

    Each slot holds exactly one token (the endpoint URL string).  Acquiring a
    slot removes the token; releasing puts it back.  This ensures at most one
    concurrent task per Chrome instance.

    Unrouted acquire() races all slots and takes whichever becomes available
    first, mimicking the previous single-queue round-robin behaviour.
    """

    def __init__(self, endpoints: list[str]) -> None:
        # One single-element queue per endpoint acting as a semaphore
        self._slots: dict[str, asyncio.Queue[str]] = {}
        for ep in endpoints:
            q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
            q.put_nowait(ep)
            self._slots[ep] = q
        self._total = len(endpoints)
        # mode per endpoint: "bridge" (opencli 1.0.0 daemon) or "cdp" (opencli 0.9.6 Playwright)
        self._modes: dict[str, str] = {ep: "bridge" for ep in endpoints}
        # agent_url per endpoint: HTTP base URL of the agent server (COLLECTION_MODE=agent only)
        self._agent_urls: dict[str, str | None] = {ep: None for ep in endpoints}
        # agent_protocol per endpoint: "http" (LAN/proxy) or "ws" (NAT reverse channel, Phase 2)
        self._agent_protocols: dict[str, str | None] = {ep: None for ep in endpoints}
        # node_type per endpoint: "chrome" (needs browser) | "shell" (runs opencli natively)
        self._node_types: dict[str, str] = {ep: "chrome" for ep in endpoints}
        logger.info(
            "BrowserPool (local): %d Chrome instance(s): %s",
            self._total,
            list(endpoints),
        )

    @asynccontextmanager
    async def acquire(self, endpoint: str | None = None) -> AsyncIterator[str]:
        if endpoint:
            if endpoint not in self._slots:
                # Requested endpoint not in pool — fall back to any available
                logger.warning(
                    "Requested Chrome endpoint %r not in pool; falling back to any instance.",
                    endpoint,
                )
                ep = await self._acquire_any()
            else:
                ep = await self._slots[endpoint].get()
                logger.debug("Chrome acquired (routed): %s", ep)
        else:
            ep = await self._acquire_any()

        try:
            yield ep
        finally:
            self._slots[ep].put_nowait(ep)
            logger.debug("Chrome released: %s", ep)

    async def _acquire_any(self) -> str:
        """Wait for whichever endpoint slot becomes free first."""
        tasks: dict[asyncio.Task[str], str] = {
            asyncio.get_event_loop().create_task(slot.get()): ep
            for ep, slot in self._slots.items()
        }
        done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
        # Cancel remaining waiters (they haven't consumed a token)
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        ep = tasks[next(iter(done))]
        logger.debug(
            "Chrome acquired (any): %s (available: %d/%d)",
            ep,
            self.available,
            self._total,
        )
        return ep

    @property
    def total(self) -> int:
        return self._total

    @property
    def available(self) -> int:
        return sum(1 for q in self._slots.values() if not q.empty())

    @property
    def endpoints(self) -> list[str]:
        return list(self._slots.keys())

    def available_for(self, endpoint: str) -> bool:
        q = self._slots.get(endpoint)
        return q is not None and not q.empty()

    def get_mode(self, endpoint: str) -> str:
        """Return the connection mode for the given endpoint ("bridge" or "cdp")."""
        return self._modes.get(endpoint, "bridge")

    def set_mode(self, endpoint: str, mode: str) -> None:
        """Update the connection mode for an endpoint at runtime."""
        self._modes[endpoint] = mode
        logger.info("BrowserPool: endpoint %s mode set to %s", endpoint, mode)

    def get_agent_url(self, endpoint: str) -> str | None:
        """Return the agent HTTP base URL for the given endpoint."""
        return self._agent_urls.get(endpoint)

    def set_agent_url(self, endpoint: str, agent_url: str | None) -> None:
        """Update the agent URL for an endpoint at runtime."""
        self._agent_urls[endpoint] = agent_url
        logger.info("BrowserPool: endpoint %s agent_url set to %s", endpoint, agent_url)

    def get_agent_protocol(self, endpoint: str) -> str | None:
        """Return the agent protocol for the given endpoint ("http", "ws", or None)."""
        return self._agent_protocols.get(endpoint)

    def set_agent_protocol(self, endpoint: str, protocol: str | None) -> None:
        """Update the agent protocol for an endpoint at runtime."""
        self._agent_protocols[endpoint] = protocol
        logger.info("BrowserPool: endpoint %s agent_protocol set to %s", endpoint, protocol)

    def get_node_type(self, endpoint: str) -> str:
        """Return deployment type: 'chrome' (uses browser) or 'shell' (native opencli)."""
        return self._node_types.get(endpoint, "chrome")

    def set_node_type(self, endpoint: str, node_type: str) -> None:
        """Update the node deployment type for an endpoint."""
        self._node_types[endpoint] = node_type
        logger.info("BrowserPool: endpoint %s node_type set to %s", endpoint, node_type)

    def add_endpoint(self, endpoint: str) -> None:
        """Hot-add a new Chrome instance to the pool without restarting."""
        if endpoint in self._slots:
            return
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        q.put_nowait(endpoint)
        self._slots[endpoint] = q
        self._modes.setdefault(endpoint, "bridge")
        self._agent_urls.setdefault(endpoint, None)
        self._agent_protocols.setdefault(endpoint, None)
        self._node_types.setdefault(endpoint, "chrome")
        self._total += 1
        logger.info("BrowserPool: added endpoint %s (total: %d)", endpoint, self._total)

    def remove_endpoint(self, endpoint: str) -> None:
        """Remove a Chrome instance from the pool (best-effort; waits for slot to be free)."""
        if endpoint not in self._slots:
            return
        self._slots.pop(endpoint)
        self._modes.pop(endpoint, None)
        self._agent_urls.pop(endpoint, None)
        self._agent_protocols.pop(endpoint, None)
        self._node_types.pop(endpoint, None)
        self._total -= 1
        logger.info("BrowserPool: removed endpoint %s (total: %d)", endpoint, self._total)


class RedisBrowserPool:
    """Distributed pool backed by Redis lists (BLPOP/RPUSH).

    Safe across multiple Celery worker processes and machines.

    Routing support:
      - Unrouted acquire() uses the shared pool list (existing behaviour).
      - Routed acquire(endpoint=...) uses a per-endpoint list key so only
        that specific Chrome instance is used, without consuming a slot from
        the shared pool.  This lets you pin data sources to Chrome instances
        that are logged into specific sites.

    Initialisation is idempotent (SET NX lock) so multiple API/worker
    replicas don't double-push endpoints.
    """

    _POOL_KEY = "browser_pool:endpoints"
    _LOCK_KEY = "browser_pool:initialized"

    @staticmethod
    def _ep_key(endpoint: str) -> str:
        """Per-endpoint Redis list key (safe characters only)."""
        safe = endpoint.replace("://", "_").replace(":", "_").replace("/", "_")
        return f"browser_pool:ep:{safe}"

    def __init__(self, endpoints: list[str], redis_url: str) -> None:
        self._endpoints = list(endpoints)
        self._redis_url = redis_url
        self._total = len(endpoints)

    def _client(self):
        import redis.asyncio as aioredis  # type: ignore[import]
        return aioredis.from_url(self._redis_url, decode_responses=True)

    async def initialize(self) -> None:
        """Populate the Redis pool and per-endpoint lists (idempotent)."""
        async with self._client() as r:
            acquired = await r.set(self._LOCK_KEY, "1", nx=True, ex=3600)
            if not acquired:
                logger.info("BrowserPool (Redis): pool already initialized by another replica")
                return

            # Shared pool list (for unrouted acquire)
            await r.delete(self._POOL_KEY)
            if self._endpoints:
                await r.rpush(self._POOL_KEY, *self._endpoints)

            # Per-endpoint lists (for routed acquire)
            for ep in self._endpoints:
                key = self._ep_key(ep)
                await r.delete(key)
                await r.rpush(key, ep)

            logger.info(
                "BrowserPool (Redis): %d Chrome instance(s) initialised",
                self._total,
            )

    @asynccontextmanager
    async def acquire(self, endpoint: str | None = None) -> AsyncIterator[str]:
        if endpoint:
            key = self._ep_key(endpoint)
            async with self._client() as r:
                result = await r.blpop(key, timeout=300)
            if result is None:
                raise TimeoutError(
                    f"Chrome instance {endpoint!r} not available within 5 minutes."
                )
            _, ep = result
            logger.debug("Chrome acquired (routed, Redis): %s", ep)
        else:
            async with self._client() as r:
                result = await r.blpop(self._POOL_KEY, timeout=300)
            if result is None:
                raise TimeoutError(
                    "No Chrome instance became available within 5 minutes. "
                    "Check that chrome containers are running."
                )
            _, ep = result
            logger.debug("Chrome acquired (any, Redis): %s", ep)

        try:
            yield ep
        finally:
            if endpoint:
                release_key = self._ep_key(ep)
            else:
                release_key = self._POOL_KEY
            async with self._client() as r:
                await r.rpush(release_key, ep)
            logger.debug("Chrome released (Redis): %s", ep)

    @property
    def total(self) -> int:
        return self._total

    @property
    def available(self) -> int:
        return -1  # unknown without a synchronous Redis call

    @property
    def endpoints(self) -> list[str]:
        return list(self._endpoints)

    def available_for(self, endpoint: str) -> bool:
        return endpoint in self._endpoints  # approximate; real check would need Redis


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
    """Async post-init step (populates Redis lists if applicable)."""
    if isinstance(_pool, RedisBrowserPool):
        await _pool.initialize()


def get_pool() -> LocalBrowserPool | RedisBrowserPool:
    if _pool is None:
        raise RuntimeError("BrowserPool not initialized — call init_pool() first")
    return _pool
