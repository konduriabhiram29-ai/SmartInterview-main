"""
SmartInterview — Chat WebSocket Gateway

Architecture:
    /ws/chat?token=<JWT>

    Each connected user has one WebSocket per instance.
    Messages are:
        1. Received from client
        2. Authenticated + validated
        3. Persisted to DB (if needed)
        4. Published to Redis (chat:group:{id})
        5. All instances deliver to their locally-connected members

    Each instance runs a per-group Redis subscriber task.
    A subscriber is started when a user joins a group, and reused across connections.

Event Protocol (centralized in schemas/chat.py WSEventType):
    message.send      → persist → ack → broadcast
    typing.start/stop → ephemeral Redis + broadcast
    presence.heartbeat → refresh Redis TTL
    ping              → pong
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import JWT_SECRET_KEY, JWT_ALGORITHM
from app.database import SessionLocal
from app.models.user import User
from app.models.chat import ChatGroupMember
from app.schemas.chat import WSEventType, WSErrorCode
from app.services import redis_service
from app.services.chat_authorization import ws_get_membership, ws_is_member, ws_is_admin
from app.services.chat_service import (
    persist_text_message, _message_to_response, mark_read,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# JWT Decode (WebSocket — query param, not header)
# ─────────────────────────────────────────────────────────────────────────────

def decode_ws_token(token: str) -> Optional[int]:
    """Decode JWT and return user_id, or None on failure."""
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except Exception:
        return None


def get_user_from_db(user_id: int) -> Optional[User]:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Connection Manager
# ─────────────────────────────────────────────────────────────────────────────

class ChatConnectionManager:
    """
    Manages active WebSocket connections for this backend instance.
    
    Structure:
        _connections: {user_id: WebSocket}
        _user_groups: {user_id: set(group_ids)}
        _group_subscribers: {group_id: asyncio.Task}  # Redis subscriber tasks
    """

    def __init__(self):
        self._connections: Dict[int, WebSocket] = {}
        self._user_groups: Dict[int, Set[int]] = {}
        self._group_subscribers: Dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int, group_ids: List[int]):
        await websocket.accept()
        async with self._lock:
            self._connections[user_id] = websocket
            self._user_groups[user_id] = set(group_ids)
            # Start Redis subscribers for groups the user belongs to
            for gid in group_ids:
                await self._ensure_subscriber(gid)

    async def disconnect(self, user_id: int):
        async with self._lock:
            self._connections.pop(user_id, None)
            self._user_groups.pop(user_id, None)
        await redis_service.set_user_offline(user_id)

    async def _ensure_subscriber(self, group_id: int):
        """Start a Redis subscriber task for this group if not already running."""
        if group_id in self._group_subscribers:
            task = self._group_subscribers[group_id]
            if not task.done():
                return
        task = await redis_service.start_group_subscriber(
            group_id,
            lambda event: self._deliver_group_event(group_id, event),
        )
        if task:
            self._group_subscribers[group_id] = task

    async def _deliver_group_event(self, group_id: int, event: dict):
        """Deliver a Redis event to all locally-connected members of this group."""
        async with self._lock:
            recipients = [
                uid for uid, groups in self._user_groups.items()
                if group_id in groups and uid in self._connections
            ]
        for uid in recipients:
            ws = self._connections.get(uid)
            if ws:
                try:
                    await ws.send_json(event)
                except Exception as exc:
                    logger.warning("WS send failed to user %s: %s", uid, exc)

    async def broadcast_to_group(self, group_id: int, event: dict):
        """
        Primary broadcast path:
        1. Publish to Redis (reaches all instances)
        2. Also deliver locally in case Redis is unavailable
        """
        published = await redis_service.publish_to_group(group_id, event)
        if not published:
            # Redis unavailable — deliver only to local connections
            await self._deliver_group_event(group_id, event)

    async def send_to_user(self, user_id: int, event: dict):
        """Send directly to a specific user on this instance."""
        ws = self._connections.get(user_id)
        if ws:
            try:
                await ws.send_json(event)
            except Exception as exc:
                logger.warning("WS direct send failed to user %s: %s", user_id, exc)

    async def add_user_to_group(self, user_id: int, group_id: int):
        """Called when a user is added to a group mid-session."""
        async with self._lock:
            if user_id in self._user_groups:
                self._user_groups[user_id].add(group_id)
            await self._ensure_subscriber(group_id)

    async def remove_user_from_group(self, user_id: int, group_id: int):
        """Called when a user is removed from a group."""
        async with self._lock:
            if user_id in self._user_groups:
                self._user_groups[user_id].discard(group_id)

    def get_connected_user_ids(self) -> List[int]:
        return list(self._connections.keys())


# Global connection manager instance (per process)
manager = ChatConnectionManager()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build error payload
# ─────────────────────────────────────────────────────────────────────────────

def _error(code: str, message: str) -> dict:
    return {"type": WSEventType.ERROR, "code": code, "message": message}


# ─────────────────────────────────────────────────────────────────────────────
# Main WebSocket Handler
# ─────────────────────────────────────────────────────────────────────────────

async def handle_chat_websocket(websocket: WebSocket, token: str):
    """
    Main WebSocket lifecycle handler.

    Flow:
        1. Authenticate via JWT token in query param
        2. Load user's active group memberships
        3. Register connection
        4. Set presence online
        5. Handle events in loop with heartbeat
        6. Clean up on disconnect
    """
    # ── 1. Authenticate ─────────────────────────────────────────────────────
    user_id = decode_ws_token(token) if token else None
    if not user_id:
        await websocket.accept()
        await websocket.send_json(_error(WSErrorCode.UNAUTHORIZED, "Invalid or missing token."))
        await websocket.close(code=4001)
        return

    user = await asyncio.to_thread(get_user_from_db, user_id)
    if not user:
        await websocket.accept()
        await websocket.send_json(_error(WSErrorCode.UNAUTHORIZED, "User not found."))
        await websocket.close(code=4001)
        return

    # ── 2. Load group memberships ────────────────────────────────────────────
    def _get_groups():
        db = SessionLocal()
        try:
            rows = (
                db.query(ChatGroupMember.group_id)
                .filter(
                    ChatGroupMember.user_id == user_id,
                    ChatGroupMember.is_active == True,
                )
                .all()
            )
            return [r.group_id for r in rows]
        finally:
            db.close()

    group_ids = await asyncio.to_thread(_get_groups)

    # ── 3. Register connection ────────────────────────────────────────────────
    await manager.connect(websocket, user_id, group_ids)
    logger.info("WS connected: user_id=%s, groups=%s", user_id, group_ids)

    # ── 4. Set presence ──────────────────────────────────────────────────────
    await redis_service.set_user_online(user_id)
    await manager.send_to_user(user_id, {"type": WSEventType.PONG, "status": "connected"})

    # Heartbeat task — refreshes presence every 30s
    heartbeat_task = asyncio.create_task(_heartbeat(user_id))

    try:
        while True:
            # Wait for message with timeout for heartbeat
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                # Connection seems stale — send ping
                await websocket.send_json({"type": WSEventType.PING})
                continue

            await _handle_event(websocket, user_id, raw)

    except WebSocketDisconnect:
        logger.info("WS disconnected: user_id=%s", user_id)
    except Exception as exc:
        logger.error("WS error for user %s: %s", user_id, exc)
    finally:
        heartbeat_task.cancel()
        await manager.disconnect(user_id)
        logger.info("WS cleanup done: user_id=%s", user_id)


async def _heartbeat(user_id: int):
    """Refresh presence every 30 seconds."""
    try:
        while True:
            await asyncio.sleep(30)
            await redis_service.set_user_online(user_id)
    except asyncio.CancelledError:
        pass


async def _handle_event(websocket: WebSocket, user_id: int, raw: str):
    """Parse and dispatch a single WebSocket event."""
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        await websocket.send_json(_error(WSErrorCode.INVALID_PAYLOAD, "Invalid JSON."))
        return

    event_type = event.get("type")

    if event_type == WSEventType.MESSAGE_SEND:
        await _handle_message_send(websocket, user_id, event)

    elif event_type == WSEventType.TYPING_START:
        await _handle_typing(websocket, user_id, event, is_typing=True)

    elif event_type == WSEventType.TYPING_STOP:
        await _handle_typing(websocket, user_id, event, is_typing=False)

    elif event_type == WSEventType.PING:
        await websocket.send_json({"type": WSEventType.PONG})

    elif event_type == WSEventType.PRESENCE_HEARTBEAT:
        await redis_service.set_user_online(user_id)

    else:
        await websocket.send_json(_error(WSErrorCode.INVALID_PAYLOAD, f"Unknown event type: {event_type}"))


async def _handle_message_send(websocket: WebSocket, user_id: int, event: dict):
    """
    Process a message.send event.
    
    Flow: auth → membership → rate limit → persist → ack → broadcast
    """
    group_id = event.get("group_id")
    content_text = event.get("content", "").strip()
    client_message_id = event.get("client_message_id")

    if not group_id or not content_text:
        await websocket.send_json(_error(WSErrorCode.INVALID_PAYLOAD, "group_id and content are required."))
        return

    # Enforce max message length
    if len(content_text) > 5000:
        await websocket.send_json(_error(WSErrorCode.INVALID_PAYLOAD, "Message too long (max 5000 chars)."))
        return

    # Rate limiting
    allowed = await redis_service.check_message_rate_limit(user_id)
    if not allowed:
        await websocket.send_json(_error(WSErrorCode.RATE_LIMITED, "Too many messages. Slow down."))
        return

    # Validate membership (DB call in thread to avoid blocking async loop)
    def _check_membership():
        db = SessionLocal()
        try:
            return ws_get_membership(db, user_id, group_id)
        finally:
            db.close()

    membership = await asyncio.to_thread(_check_membership)
    if not ws_is_member(membership):
        await websocket.send_json(_error(WSErrorCode.NOT_MEMBER, "You are not a member of this group."))
        return

    # Persist message (in thread)
    def _persist():
        db = SessionLocal()
        try:
            return persist_text_message(
                db, user_id, group_id, content_text,
                client_message_id=client_message_id,
                reply_to_id=event.get("reply_to_id"),
            )
        finally:
            db.close()

    try:
        msg = await asyncio.to_thread(_persist)
    except Exception as exc:
        logger.error("Message persist failed: %s", exc)
        await websocket.send_json(_error(WSErrorCode.SERVER_ERROR, "Failed to save message."))
        return

    # Acknowledgment to sender
    ack = {
        "type": WSEventType.MESSAGE_ACK,
        "client_message_id": client_message_id,
        "message_id": msg.id,
        "status": "sent",
        "timestamp": msg.created_at.isoformat(),
    }
    await websocket.send_json(ack)

    # Broadcast to group (via Redis → all instances)
    broadcast = {
        "type": WSEventType.MESSAGE_NEW,
        "message": _message_to_response(msg),
    }
    await manager.broadcast_to_group(group_id, broadcast)


async def _handle_typing(websocket: WebSocket, user_id: int, event: dict, is_typing: bool):
    """Ephemeral typing indicator — never persisted to DB."""
    group_id = event.get("group_id")
    if not group_id:
        return

    # Quick membership check (non-blocking via Redis presence)
    await redis_service.set_typing(group_id, user_id, is_typing)

    typing_event = {
        "type": WSEventType.TYPING,
        "group_id": group_id,
        "user_id": user_id,
        "is_typing": is_typing,
    }
    await manager.broadcast_to_group(group_id, typing_event)
