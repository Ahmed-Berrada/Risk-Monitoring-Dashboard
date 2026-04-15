"""
Server-Sent Events (SSE) stream.

Pushes real-time updates to the frontend when:
- Risk metrics are recomputed (risk_updated)
- Alerts are triggered (alert_triggered)

SSE is HTTP-native, auto-reconnects, and is perfect for
one-directional server → client push of event data.
"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["stream"])

# ── In-memory broadcast channel ─────────────────────────────────────────────

# Simple asyncio.Queue-based fan-out. Each connected SSE client
# gets its own queue. When an event arrives, it's pushed to all queues.

_clients: list[asyncio.Queue] = []


async def broadcast(event_type: str, data: dict) -> None:
    """Push an event to all connected SSE clients."""
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    dead = []
    for i, queue in enumerate(_clients):
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            dead.append(i)
    # Clean up dead clients
    for i in reversed(dead):
        _clients.pop(i)


# ── SSE Endpoint ─────────────────────────────────────────────────────────────


@router.get("/api/stream")
async def sse_stream(request: Request):
    """
    SSE endpoint. Clients connect here to receive real-time updates.

    Event types:
      - risk_updated: new risk metrics available
      - alert_triggered: alert threshold breached
      - heartbeat: keep-alive every 30s
    """

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        _clients.append(queue)
        logger.info("sse.client_connected", total_clients=len(_clients))

        try:
            # Send initial connection event
            yield _format_sse("connected", {"message": "SSE stream active"})

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with timeout for heartbeat
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield _format_sse(message["type"], message["data"])
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield _format_sse("heartbeat", {
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

        except asyncio.CancelledError:
            pass
        finally:
            if queue in _clients:
                _clients.remove(queue)
            logger.info("sse.client_disconnected", total_clients=len(_clients))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


def _format_sse(event_type: str, data: dict) -> str:
    """Format data as an SSE message."""
    payload = json.dumps(data)
    return f"event: {event_type}\ndata: {payload}\n\n"
