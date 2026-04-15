"""
Internal event bus using PostgreSQL LISTEN/NOTIFY.

This is the core of our event-driven modular monolith.
Services emit events after completing work, and other services
subscribe to those events to trigger their own processing.

Events:
  - data_refreshed: New OHLCV data has been ingested
  - risk_updated:   Risk metrics have been recomputed
  - alert_triggered: An alert threshold has been breached
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Callable, Awaitable
from dataclasses import dataclass, field

import asyncpg
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

# ── Event Types ──────────────────────────────────────────────────────────────

EVENTS = {
    "data_refreshed",
    "risk_updated",
    "alert_triggered",
}


@dataclass
class Event:
    channel: str
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Event Bus ────────────────────────────────────────────────────────────────

EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """PostgreSQL LISTEN/NOTIFY-based event bus."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._conn: asyncpg.Connection | None = None
        self._listening = False

    def subscribe(self, channel: str, handler: EventHandler) -> None:
        """Register an async handler for an event channel."""
        if channel not in EVENTS:
            raise ValueError(f"Unknown event channel: {channel}. Must be one of {EVENTS}")
        self._handlers.setdefault(channel, []).append(handler)
        logger.info("event_bus.subscribed", channel=channel, handler=handler.__name__)

    async def publish(self, event: Event) -> None:
        """Publish an event via PostgreSQL NOTIFY."""
        settings = get_settings()
        # Parse the async DSN to get a regular connection string for asyncpg
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            payload = json.dumps({"payload": event.payload, "timestamp": event.timestamp})
            await conn.execute(f"NOTIFY {event.channel}, '{payload}'")
            logger.info("event_bus.published", channel=event.channel, payload=event.payload)
        finally:
            await conn.close()

    async def start_listening(self) -> None:
        """Start listening for NOTIFY events on all subscribed channels."""
        if not self._handlers:
            logger.warning("event_bus.no_handlers", msg="No handlers registered, skipping listener")
            return

        settings = get_settings()
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        self._conn = await asyncpg.connect(dsn)
        self._listening = True

        for channel in self._handlers:
            await self._conn.add_listener(channel, self._on_notification)
            logger.info("event_bus.listening", channel=channel)

    def _on_notification(
        self, connection: asyncpg.Connection, pid: int, channel: str, payload: str
    ) -> None:
        """Handle incoming NOTIFY — dispatch to registered handlers."""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = {"raw": payload}

        event = Event(
            channel=channel,
            payload=data.get("payload", data),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )

        handlers = self._handlers.get(channel, [])
        for handler in handlers:
            asyncio.create_task(self._safe_handle(handler, event))

    async def _safe_handle(self, handler: EventHandler, event: Event) -> None:
        """Run handler with error catching so one failure doesn't break the bus."""
        try:
            await handler(event)
        except Exception:
            logger.exception("event_bus.handler_error", handler=handler.__name__, event=event.channel)

    async def stop(self) -> None:
        """Stop listening and close the connection."""
        self._listening = False
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("event_bus.stopped")


# ── Singleton ────────────────────────────────────────────────────────────────

event_bus = EventBus()
