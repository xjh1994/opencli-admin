"""
Live integration tests — Weibo & Zhihu collection via Shell deployment.

Requires a running API server and opencli daemon.  Skipped automatically
when the server is not reachable or opencli is not installed.

Run:
    # 1. Deploy (see TESTING.md Shell section):
    #    Chrome --remote-debugging-port=9222
    #    node $(npm root -g)/@jackwener/opencli/dist/daemon.js &
    #    OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9222 COLLECTION_MODE=local \\
    #        .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
    #
    # 2. Run these tests:
    #    BASE_URL=http://localhost:8000 pytest tests/integration/test_weibo_zhihu_collection.py -v -m live
"""

import asyncio
import os
import shutil

import pytest
import pytest_asyncio
import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
POLL_INTERVAL = int(os.environ.get("LIVE_POLL_INTERVAL", "5"))
POLL_TIMEOUT = int(os.environ.get("LIVE_POLL_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------

def _server_reachable() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{BASE_URL}/api/v1/sources", timeout=3)  # noqa: S310
        return True
    except Exception:
        return False


def _opencli_installed() -> bool:
    return shutil.which("opencli") is not None


skip_no_server = pytest.mark.skipif(
    not _server_reachable(),
    reason=f"Live API server not reachable at {BASE_URL}",
)

skip_no_opencli = pytest.mark.skipif(
    not _opencli_installed(),
    reason="opencli not found in PATH — run: npm install -g @jackwener/opencli@1.7.4",
)

pytestmark = [pytest.mark.live, skip_no_server, skip_no_opencli]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def live_client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_source(client: httpx.AsyncClient, name: str, site: str, command: str) -> str:
    resp = await client.post(
        "/api/v1/sources",
        json={
            "name": name,
            "channel_type": "opencli",
            "channel_config": {
                "site": site,
                "command": command,
                "args": {},
                "format": "json",
            },
            "enabled": True,
        },
    )
    assert resp.status_code == 201, f"create source failed: {resp.text}"
    return resp.json()["data"]["id"]


async def trigger_task(client: httpx.AsyncClient, source_id: str) -> str:
    resp = await client.post(
        "/api/v1/tasks/trigger",
        json={"source_id": source_id, "trigger_type": "manual"},
    )
    assert resp.status_code == 202, f"trigger task failed: {resp.text}"
    return resp.json()["data"]["task_id"]


async def poll_task_run(
    client: httpx.AsyncClient,
    task_id: str,
    timeout: int = POLL_TIMEOUT,
    interval: int = POLL_INTERVAL,
) -> dict:
    elapsed = 0
    while elapsed < timeout:
        resp = await client.get(f"/api/v1/tasks/{task_id}/runs?limit=1")
        assert resp.status_code == 200
        runs = resp.json()["data"]
        if runs:
            run = runs[0]
            if run["status"] in ("completed", "failed", "error"):
                return run
        await asyncio.sleep(interval)
        elapsed += interval
    pytest.fail(f"task {task_id} did not finish within {timeout}s")


async def cleanup_source(client: httpx.AsyncClient, source_id: str) -> None:
    await client.delete(f"/api/v1/sources/{source_id}")


# ---------------------------------------------------------------------------
# Test: Weibo hot — Shell + local + bridge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weibo_hot_collection_bridge(live_client: httpx.AsyncClient):
    """Create a Weibo hot-list source and run a collection task (bridge mode)."""
    source_id = await create_source(
        live_client,
        name="Live-Test-Weibo-Hot-Bridge",
        site="weibo",
        command="hot",
    )
    try:
        task_id = await trigger_task(live_client, source_id)
        run = await poll_task_run(live_client, task_id)

        assert run["status"] == "completed", (
            f"expected completed, got {run['status']}; error={run.get('error_message')}"
        )
        assert run.get("records_collected", 0) > 0, (
            "completed but records_collected=0 — check opencli weibo hot output"
        )
    finally:
        await cleanup_source(live_client, source_id)


# ---------------------------------------------------------------------------
# Test: Zhihu hot — Shell + local + bridge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zhihu_hot_collection_bridge(live_client: httpx.AsyncClient):
    """Create a Zhihu hot-list source and run a collection task (bridge mode)."""
    source_id = await create_source(
        live_client,
        name="Live-Test-Zhihu-Hot-Bridge",
        site="zhihu",
        command="hot",
    )
    try:
        task_id = await trigger_task(live_client, source_id)
        run = await poll_task_run(live_client, task_id)

        assert run["status"] == "completed", (
            f"expected completed, got {run['status']}; error={run.get('error_message')}"
        )
        assert run.get("records_collected", 0) > 0, (
            "completed but records_collected=0 — check opencli zhihu hot output"
        )
    finally:
        await cleanup_source(live_client, source_id)


# ---------------------------------------------------------------------------
# Test: Weibo hot — Shell + local + CDP
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weibo_hot_collection_cdp(live_client: httpx.AsyncClient):
    """Switch chrome-pool to CDP mode then collect Weibo hot-list."""
    import base64
    cdp_endpoint = os.environ.get("CDP_ENDPOINT", "http://127.0.0.1:9222")
    ep_b64 = base64.urlsafe_b64encode(cdp_endpoint.encode()).decode()

    switch_resp = await live_client.patch(
        f"/api/v1/workers/chrome-pool/{ep_b64}/mode",
        json={"mode": "cdp"},
    )
    assert switch_resp.status_code == 200, f"mode switch failed: {switch_resp.text}"

    source_id = await create_source(
        live_client,
        name="Live-Test-Weibo-Hot-CDP",
        site="weibo",
        command="hot",
    )
    try:
        task_id = await trigger_task(live_client, source_id)
        run = await poll_task_run(live_client, task_id)

        assert run["status"] == "completed", (
            f"expected completed, got {run['status']}; error={run.get('error_message')}"
        )
        assert run.get("records_collected", 0) > 0
    finally:
        await cleanup_source(live_client, source_id)
        # Restore bridge mode
        await live_client.patch(
            f"/api/v1/workers/chrome-pool/{ep_b64}/mode",
            json={"mode": "bridge"},
        )


# ---------------------------------------------------------------------------
# Test: Zhihu hot — Shell + local + CDP
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zhihu_hot_collection_cdp(live_client: httpx.AsyncClient):
    """Switch chrome-pool to CDP mode then collect Zhihu hot-list."""
    import base64
    cdp_endpoint = os.environ.get("CDP_ENDPOINT", "http://127.0.0.1:9222")
    ep_b64 = base64.urlsafe_b64encode(cdp_endpoint.encode()).decode()

    switch_resp = await live_client.patch(
        f"/api/v1/workers/chrome-pool/{ep_b64}/mode",
        json={"mode": "cdp"},
    )
    assert switch_resp.status_code == 200, f"mode switch failed: {switch_resp.text}"

    source_id = await create_source(
        live_client,
        name="Live-Test-Zhihu-Hot-CDP",
        site="zhihu",
        command="hot",
    )
    try:
        task_id = await trigger_task(live_client, source_id)
        run = await poll_task_run(live_client, task_id)

        assert run["status"] == "completed", (
            f"expected completed, got {run['status']}; error={run.get('error_message')}"
        )
        assert run.get("records_collected", 0) > 0
    finally:
        await cleanup_source(live_client, source_id)
        await live_client.patch(
            f"/api/v1/workers/chrome-pool/{ep_b64}/mode",
            json={"mode": "bridge"},
        )


# ---------------------------------------------------------------------------
# Test: concurrent Weibo + Zhihu (smoke test for parallel tasks)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weibo_and_zhihu_concurrent(live_client: httpx.AsyncClient):
    """Trigger Weibo and Zhihu collection concurrently and verify both complete."""
    weibo_id = await create_source(live_client, "Live-Test-Concurrent-Weibo", "weibo", "hot")
    zhihu_id = await create_source(live_client, "Live-Test-Concurrent-Zhihu", "zhihu", "hot")
    try:
        weibo_task, zhihu_task = await asyncio.gather(
            trigger_task(live_client, weibo_id),
            trigger_task(live_client, zhihu_id),
        )
        weibo_run, zhihu_run = await asyncio.gather(
            poll_task_run(live_client, weibo_task),
            poll_task_run(live_client, zhihu_task),
        )

        assert weibo_run["status"] == "completed", (
            f"Weibo: {weibo_run['status']} — {weibo_run.get('error_message')}"
        )
        assert zhihu_run["status"] == "completed", (
            f"Zhihu: {zhihu_run['status']} — {zhihu_run.get('error_message')}"
        )
        assert weibo_run.get("records_collected", 0) > 0
        assert zhihu_run.get("records_collected", 0) > 0
    finally:
        await asyncio.gather(
            cleanup_source(live_client, weibo_id),
            cleanup_source(live_client, zhihu_id),
        )
