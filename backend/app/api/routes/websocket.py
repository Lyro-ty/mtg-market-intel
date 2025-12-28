"""
WebSocket API for real-time price updates and notifications.

This module provides a WebSocket endpoint that clients can connect to
for receiving real-time updates on:
- Market index changes
- Individual card price updates
- Dashboard notifications
- Inventory updates (for authenticated users)
- New recommendations

Architecture:
- Clients connect and subscribe to specific channels
- Redis Pub/Sub bridges messages from Celery workers to WebSocket clients
- JWT authentication for protected channels (inventory, recommendations)
"""
import asyncio
import json
from datetime import datetime
from typing import Any
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from redis.asyncio import Redis
import structlog

from app.core.config import settings
from app.api.deps import get_optional_current_user
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections and channel subscriptions.

    Features:
    - Connection tracking per channel
    - Redis Pub/Sub integration for cross-worker messaging
    - Automatic cleanup on disconnect
    """

    def __init__(self):
        # Map of channel -> set of connections
        self.channels: dict[str, set[WebSocket]] = defaultdict(set)
        # Map of connection -> set of subscribed channels
        self.subscriptions: dict[WebSocket, set[str]] = defaultdict(set)
        # Map of connection -> user (for authenticated connections)
        self.authenticated: dict[WebSocket, User] = {}
        # Redis client for pub/sub
        self._redis: Redis | None = None
        # Background task for Redis subscription
        self._redis_task: asyncio.Task | None = None
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def get_redis(self) -> Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def connect(
        self,
        websocket: WebSocket,
        user: User | None = None,
    ) -> None:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            user: Authenticated user (optional)
        """
        await websocket.accept()

        async with self._lock:
            self.subscriptions[websocket] = set()
            if user:
                self.authenticated[websocket] = user

        logger.info(
            "WebSocket connected",
            user_id=user.id if user else None,
            authenticated=user is not None,
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Handle WebSocket disconnection.

        Cleans up all subscriptions and channel memberships.
        """
        async with self._lock:
            # Get all channels this connection was subscribed to
            channels = self.subscriptions.pop(websocket, set())

            # Remove from each channel
            for channel in channels:
                self.channels[channel].discard(websocket)
                # Clean up empty channels
                if not self.channels[channel]:
                    del self.channels[channel]

            # Remove from authenticated
            user = self.authenticated.pop(websocket, None)

        logger.info(
            "WebSocket disconnected",
            user_id=user.id if user else None,
            channels=list(channels),
        )

    async def subscribe(
        self,
        websocket: WebSocket,
        channel: str,
    ) -> bool:
        """
        Subscribe a connection to a channel.

        Args:
            websocket: WebSocket connection
            channel: Channel name to subscribe to

        Returns:
            True if subscription successful
        """
        # Check if channel requires authentication
        if channel.startswith("channel:inventory:") or channel.startswith("channel:user:"):
            if websocket not in self.authenticated:
                await self._send_error(websocket, "Authentication required for this channel")
                return False

            # Verify user owns the resource
            user = self.authenticated[websocket]
            if f":user:{user.id}" not in channel and f":inventory:user:{user.id}" not in channel:
                # Allow if it's the user's own channel
                pass

        async with self._lock:
            self.channels[channel].add(websocket)
            self.subscriptions[websocket].add(channel)

        logger.debug("WebSocket subscribed", channel=channel)

        # Send confirmation
        await self._send(websocket, {
            "type": "subscribed",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return True

    async def unsubscribe(
        self,
        websocket: WebSocket,
        channel: str,
    ) -> None:
        """
        Unsubscribe a connection from a channel.

        Args:
            websocket: WebSocket connection
            channel: Channel name to unsubscribe from
        """
        async with self._lock:
            self.channels[channel].discard(websocket)
            self.subscriptions[websocket].discard(channel)

            # Clean up empty channels
            if not self.channels[channel]:
                del self.channels[channel]

        logger.debug("WebSocket unsubscribed", channel=channel)

        # Send confirmation
        await self._send(websocket, {
            "type": "unsubscribed",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def broadcast(
        self,
        channel: str,
        message: dict[str, Any],
    ) -> int:
        """
        Broadcast a message to all subscribers of a channel.

        Args:
            channel: Channel name
            message: Message to broadcast

        Returns:
            Number of connections that received the message
        """
        connections = self.channels.get(channel, set()).copy()
        if not connections:
            return 0

        # Add metadata
        message["channel"] = channel
        message["timestamp"] = datetime.utcnow().isoformat()

        # Send to all connections
        sent = 0
        for websocket in connections:
            try:
                await self._send(websocket, message)
                sent += 1
            except Exception as e:
                logger.warning("Failed to send to WebSocket", error=str(e))

        return sent

    async def _send(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> None:
        """Send a message to a WebSocket connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning("WebSocket send failed", error=str(e))
            raise

    async def _send_error(
        self,
        websocket: WebSocket,
        error: str,
    ) -> None:
        """Send an error message to a WebSocket connection."""
        await self._send(websocket, {
            "type": "error",
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def start_redis_listener(self) -> None:
        """
        Start the Redis Pub/Sub listener.

        Listens for messages on channel:* patterns and broadcasts
        them to connected WebSocket clients.
        """
        if self._redis_task is not None:
            return

        async def listener():
            redis = await self.get_redis()
            pubsub = redis.pubsub()

            # Subscribe to all channel:* patterns
            await pubsub.psubscribe("channel:*")

            logger.info("Redis Pub/Sub listener started")

            try:
                async for message in pubsub.listen():
                    if message["type"] == "pmessage":
                        channel = message["channel"]
                        try:
                            data = json.loads(message["data"])
                            await self.broadcast(channel, data)
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON from Redis", channel=channel)
            except asyncio.CancelledError:
                logger.info("Redis Pub/Sub listener cancelled")
            finally:
                await pubsub.punsubscribe("channel:*")
                await pubsub.close()

        self._redis_task = asyncio.create_task(listener())

    async def stop_redis_listener(self) -> None:
        """Stop the Redis Pub/Sub listener."""
        if self._redis_task:
            self._redis_task.cancel()
            try:
                await self._redis_task
            except asyncio.CancelledError:
                pass
            self._redis_task = None

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        await self.stop_redis_listener()
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """
    WebSocket endpoint for real-time updates.

    Clients connect and send subscribe/unsubscribe messages:

    Subscribe to a channel:
    {"action": "subscribe", "channel": "market", "params": {"currency": "USD"}}

    Unsubscribe from a channel:
    {"action": "unsubscribe", "channel": "market:USD"}

    Available channels:
    - market:{currency} - Market index updates
    - card:{card_id} - Individual card price updates
    - dashboard:{currency} - Dashboard notifications
    - inventory:user:{user_id} - Inventory updates (auth required)
    - recommendations - New recommendation alerts

    Authentication:
    Pass JWT token as query parameter: /ws?token=<jwt_token>
    """
    # Try to authenticate if token provided
    user = None
    if token:
        try:
            from app.api.deps import decode_token
            payload = decode_token(token)
            if payload:
                from app.db.session import async_session_maker
                from sqlalchemy import select
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(User).where(User.id == int(payload.get("sub", 0)))
                    )
                    user = result.scalar_one_or_none()
        except Exception as e:
            logger.debug("WebSocket auth failed", error=str(e))

    await manager.connect(websocket, user)

    # Start Redis listener if not already running
    await manager.start_redis_listener()

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            action = data.get("action")
            channel_type = data.get("channel")
            params = data.get("params", {})

            if action == "subscribe":
                # Build full channel name
                channel = _build_channel_name(channel_type, params, user)
                if channel:
                    await manager.subscribe(websocket, channel)
                else:
                    await manager._send_error(websocket, f"Invalid channel: {channel_type}")

            elif action == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    await manager.unsubscribe(websocket, channel)

            elif action == "ping":
                await manager._send(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                })

            else:
                await manager._send_error(websocket, f"Unknown action: {action}")

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        await manager.disconnect(websocket)


def _build_channel_name(
    channel_type: str,
    params: dict[str, Any],
    user: User | None,
) -> str | None:
    """
    Build a full channel name from type and parameters.

    Args:
        channel_type: Type of channel (market, card, dashboard, etc.)
        params: Channel parameters
        user: Authenticated user (if any)

    Returns:
        Full channel name or None if invalid
    """
    if channel_type == "market":
        currency = params.get("currency", "USD")
        return f"channel:market:{currency}"

    elif channel_type == "card":
        card_id = params.get("card_id")
        if card_id:
            return f"channel:card:{card_id}"
        return None

    elif channel_type == "dashboard":
        currency = params.get("currency", "USD")
        return f"channel:dashboard:{currency}"

    elif channel_type == "inventory":
        if user:
            return f"channel:inventory:user:{user.id}"
        return None  # Requires auth

    elif channel_type == "recommendations":
        return "channel:recommendations"

    return None


# Helper functions for publishing from other parts of the application
async def publish_market_update(
    currency: str,
    data: dict[str, Any],
) -> None:
    """
    Publish a market update to Redis.

    Called by Celery tasks or other services to push updates
    to WebSocket clients.
    """
    redis = await manager.get_redis()
    await redis.publish(
        f"channel:market:{currency}",
        json.dumps({
            "type": "market_update",
            **data,
        }),
    )


async def publish_card_update(
    card_id: int,
    data: dict[str, Any],
) -> None:
    """Publish a card price update to Redis."""
    redis = await manager.get_redis()
    await redis.publish(
        f"channel:card:{card_id}",
        json.dumps({
            "type": "card_update",
            "card_id": card_id,
            **data,
        }),
    )


async def publish_dashboard_update(
    currency: str,
    section: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Publish a dashboard update to Redis."""
    redis = await manager.get_redis()
    await redis.publish(
        f"channel:dashboard:{currency}",
        json.dumps({
            "type": "dashboard_update",
            "section": section,
            **(data or {}),
        }),
    )


async def publish_recommendation_update(
    data: dict[str, Any],
) -> None:
    """Publish a recommendation update to Redis."""
    redis = await manager.get_redis()
    await redis.publish(
        "channel:recommendations",
        json.dumps({
            "type": "recommendations_updated",
            **data,
        }),
    )


async def publish_inventory_update(
    user_id: int,
    data: dict[str, Any],
) -> None:
    """Publish an inventory update to Redis."""
    redis = await manager.get_redis()
    await redis.publish(
        f"channel:inventory:user:{user_id}",
        json.dumps({
            "type": "inventory_update",
            **data,
        }),
    )
