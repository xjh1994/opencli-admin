"""Center-side manager for reverse WebSocket connections from edge agents.

When an edge agent cannot be reached by the center (NAT, firewall), it initiates
a persistent WebSocket connection to the center instead. The center dispatches
collect tasks by sending JSON messages down this connection and awaiting results.

Protocol:
  1. Agent connects to  ws(s)://{center}/api/v1/browsers/agents/ws
  2. Agent → center:  {"type": "register", "agent_url": "...", "mode": "bridge", "label": "..."}
  3. Center → agent:  {"type": "registered", "agent_url": "..."}
  4. Center → agent:  {"type": "collect", "request_id": "<uuid>", "site": "...", ...}
  5. Agent → center:  {"type": "result", "request_id": "<uuid>", "success": true, "items": [...]}
  6. Either side:      {"type": "ping"} / {"type": "pong"}
"""

import asyncio
import logging
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# agent_url → active WebSocket connection
_connections: dict[str, WebSocket] = {}

# request_id → Future awaiting agent result
_pending: dict[str, asyncio.Future] = {}


def register_connection(agent_url: str, ws: WebSocket) -> None:
    """Record a newly-established WS connection for agent_url."""
    _connections[agent_url] = ws
    logger.info("WS agent connected: %s (total=%d)", agent_url, len(_connections))


def unregister_connection(agent_url: str) -> None:
    """Remove a WS connection and fail all its pending futures."""
    _connections.pop(agent_url, None)
    logger.info("WS agent disconnected: %s (remaining=%d)", agent_url, len(_connections))


def is_connected(agent_url: str) -> bool:
    return agent_url in _connections


def list_connected() -> list[str]:
    return list(_connections.keys())


async def dispatch_collect(
    agent_url: str,
    site: str,
    command: str,
    args: dict[str, Any],
    output_format: str,
    mode: str,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Send a collect task to a WS agent and await the result dict.

    Raises:
        RuntimeError: agent is not connected.
        TimeoutError: agent did not respond within *timeout* seconds.
    """
    if timeout is None:
        from backend.config import get_settings
        timeout = float(get_settings().agent_ws_timeout)

    ws = _connections.get(agent_url)
    if ws is None:
        raise RuntimeError(f"No active WS connection for agent: {agent_url}")

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[dict] = loop.create_future()
    _pending[request_id] = fut

    try:
        await ws.send_json({
            "type": "collect",
            "request_id": request_id,
            "site": site,
            "command": command,
            "args": args,
            "format": output_format,
            "mode": mode,
        })
        logger.debug("WS dispatch | agent=%s request_id=%s site=%s cmd=%s",
                     agent_url, request_id, site, command)
        return await asyncio.wait_for(fut, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"WS agent {agent_url!r} did not respond in {timeout}s")
    finally:
        _pending.pop(request_id, None)


def resolve_response(request_id: str, result: dict[str, Any]) -> None:
    """Called from the WS receive loop when an agent returns a 'result' message."""
    fut = _pending.get(request_id)
    if fut is None or fut.done():
        logger.warning("WS: unexpected result for request_id=%s (no waiting future)", request_id)
        return
    fut.set_result(result)
