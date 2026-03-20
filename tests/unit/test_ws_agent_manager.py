"""Unit tests for backend/ws_agent_manager.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.ws_agent_manager as mgr


@pytest.fixture(autouse=True)
def clear_state():
    """Ensure module-level dicts are clean before each test."""
    mgr._connections.clear()
    mgr._pending.clear()
    yield
    mgr._connections.clear()
    mgr._pending.clear()


# ── register / unregister / queries ───────────────────────────────────────────

def test_register_and_is_connected():
    ws = MagicMock()
    mgr.register_connection("http://agent:19823", ws)
    assert mgr.is_connected("http://agent:19823") is True


def test_unregister_removes_connection():
    ws = MagicMock()
    mgr.register_connection("http://agent:19823", ws)
    mgr.unregister_connection("http://agent:19823")
    assert mgr.is_connected("http://agent:19823") is False


def test_unregister_nonexistent_no_error():
    mgr.unregister_connection("http://nonexistent:19823")  # must not raise


def test_list_connected_returns_urls():
    mgr.register_connection("http://a:1", MagicMock())
    mgr.register_connection("http://b:2", MagicMock())
    connected = mgr.list_connected()
    assert "http://a:1" in connected
    assert "http://b:2" in connected
    assert len(connected) == 2


def test_is_connected_false_for_unknown():
    assert mgr.is_connected("http://nobody:19823") is False


# ── dispatch_collect: not connected ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_collect_raises_when_not_connected():
    with pytest.raises(RuntimeError, match="No active WS connection"):
        await mgr.dispatch_collect("http://missing:19823", "site", "cmd", {}, "json", "bridge")


# ── dispatch_collect: success ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_collect_success():
    """dispatch_collect sends JSON to WS and resolves the future when result arrives."""
    ws = AsyncMock()
    mgr.register_connection("http://agent:19823", ws)

    result_payload = {"success": True, "items": [{"id": 1}], "error": None}

    async def fake_send_json(payload):
        # Simulate agent responding right away
        request_id = payload["request_id"]
        asyncio.get_running_loop().call_soon(
            mgr.resolve_response, request_id, result_payload
        )

    ws.send_json = AsyncMock(side_effect=fake_send_json)

    result = await mgr.dispatch_collect(
        "http://agent:19823", "bilibili", "hot", {}, "json", "bridge", timeout=5.0
    )

    assert result["success"] is True
    assert result["items"] == [{"id": 1}]
    ws.send_json.assert_awaited_once()
    sent = ws.send_json.call_args[0][0]
    assert sent["type"] == "collect"
    assert sent["site"] == "bilibili"
    assert sent["command"] == "hot"


# ── dispatch_collect: timeout ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_collect_timeout():
    """dispatch_collect raises TimeoutError when agent does not respond."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()  # send succeeds but no resolve comes back
    mgr.register_connection("http://agent:19823", ws)

    with pytest.raises(TimeoutError, match="did not respond"):
        await mgr.dispatch_collect(
            "http://agent:19823", "site", "cmd", {}, "json", "bridge", timeout=0.05
        )


# ── dispatch_collect: pending cleaned up on timeout ──────────────────────────

@pytest.mark.asyncio
async def test_dispatch_collect_pending_cleaned_up_on_timeout():
    """After a timeout, the pending future is removed from _pending."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    mgr.register_connection("http://agent:19823", ws)

    with pytest.raises(TimeoutError):
        await mgr.dispatch_collect(
            "http://agent:19823", "s", "c", {}, "json", "bridge", timeout=0.05
        )

    assert len(mgr._pending) == 0


# ── resolve_response: unknown request_id ──────────────────────────────────────

def test_resolve_response_unknown_request_id_no_error():
    """resolve_response with unknown request_id must not raise."""
    mgr.resolve_response("nonexistent-id", {"success": True, "items": []})


# ── resolve_response: already-done future ─────────────────────────────────────

def test_resolve_response_already_done_future_no_error():
    """resolve_response on a future that's already resolved must not raise."""
    loop = asyncio.new_event_loop()
    fut = loop.create_future()
    fut.set_result({"done": True})
    mgr._pending["req-done"] = fut
    # Should log a warning but not raise
    mgr.resolve_response("req-done", {"success": True})
    loop.close()
