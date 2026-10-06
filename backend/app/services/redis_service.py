"""
SmartInterview — Redis Service

Provides:
    - Async Redis client (redis.asyncio)
    - Pub/Sub for cross-instance WebSocket broadcasting
    - Presence management (TTL-based, never written to MySQL)
    - Typing indicator management (ephemeral)
    - Rate limiting (sliding window)
    - Graceful degradation when Redis is unavailable

Architecture:
    Each message is published to: chat:group:{group_id}
    Each FastAPI instance subscribes and delivers to local WS connections.
"""

import asyncio
import json
import logging
import time
from typing import Optional, Callable, Awaitable

from app.config import REDIS_URL

logger = logging.getLogger(__name__)

# ── TTL Constants (seconds) ───────────────────────────────────────────────────
PRESENCE_TTL        = 65     # expire 5s after heartbeat interval of 60s
TYPING_TTL          = 4      # typing indicator expires after 4s of silence
GROUP_MEMBER_CACHE  = 30     # membership cache TTL

# ── Rate Limit Constants ───────────────────────────────────────────────────────
RATE_LIMIT_MESSAGES    = 20  # max messages per window
RATE_LIMIT_WINDOW      = 10  # seconds per window
RATE_LIMIT_GROUP_CREATE = 5  # max group creates per minute

_redis_client = None
_redis_available = False


async def get_redis():
    """Return the shared async Redis client (lazy init)."""
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client if _redis_available else None
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await _redis_client.ping()
        _redis_available = True
        logger.info("Redis connected: %s", REDIS_URL)
    except Exception as exc:
        _redis_available = False
        logger.warning("Redis unavailable (%s). Chat will work in single-instance mode.", exc)
        _redis_client = None
    return _redis_client if _redis_available else None


async def close_redis():
    global _redis_client, _redis_available
    if _redis_client:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
    _redis_client = None
    _redis_available = False


# ─────────────────────────────────────────────────────────────────────────────
# Pub/Sub
# ─────────────────────────────────────────────────────────────────────────────

def _group_channel(group_id: int) -> str:
    return f"chat:group:{group_id}"


async def publish_to_group(group_id: int, event: dict) -> bool:
    """Publish a chat event to all backend instances subscribed to this group."""
    redis = await get_redis()
    if not redis:
        return False
    try:
        payload = json.dumps(event, default=str)
        await redis.publish(_group_channel(group_id), payload)
        return True
    except Exception as exc:
        logger.error("Redis publish failed for group %s: %s", group_id, exc)
        return False


async def start_group_subscriber(
    group_id: int,
    callback: Callable[[dict], Awaitable[None]],
) -> Optional[asyncio.Task]:
    """
    Subscribe to a group channel and call `callback(event_dict)` for each message.
    Returns the asyncio Task so the caller can cancel it.
    """
    redis = await get_redis()
    if not redis:
        return None

    async def _listen():
        import redis.asyncio as aioredis
        # Use a separate connection for pub/sub
        sub_client = aioredis.from_url(
            REDIS_URL, encoding="utf-8", decode_responses=True
        )
        try:
            async with sub_client.pubsub() as pubsub:
                await pubsub.subscribe(_group_channel(group_id))
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        try:
                            event = json.loads(msg["data"])
                            await callback(event)
                        except Exception as exc:
                            logger.error("Subscriber callback error: %s", exc)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Subscriber loop error for group %s: %s", group_id, exc)
        finally:
            try:
                await sub_client.aclose()
            except Exception:
                pass

    return asyncio.create_task(_listen())


# ─────────────────────────────────────────────────────────────────────────────
# Presence
# ─────────────────────────────────────────────────────────────────────────────

def _presence_key(user_id: int) -> str:
    return f"presence:user:{user_id}"


async def set_user_online(user_id: int) -> None:
    """Mark user as online. Called on WS connect and heartbeat."""
    redis = await get_redis()
    if not redis:
        return
    try:
        await redis.setex(_presence_key(user_id), PRESENCE_TTL, "1")
    except Exception as exc:
        logger.warning("Presence set failed for user %s: %s", user_id, exc)


async def set_user_offline(user_id: int) -> None:
    """Remove presence key immediately on WS disconnect."""
    redis = await get_redis()
    if not redis:
        return
    try:
        await redis.delete(_presence_key(user_id))
    except Exception as exc:
        logger.warning("Presence delete failed for user %s: %s", user_id, exc)


async def get_online_user_ids(user_ids: list[int]) -> set[int]:
    """Return which of the given user_ids are currently online."""
    redis = await get_redis()
    if not redis or not user_ids:
        return set()
    try:
        keys = [_presence_key(uid) for uid in user_ids]
        results = await redis.mget(keys)
        return {uid for uid, val in zip(user_ids, results) if val is not None}
    except Exception as exc:
        logger.warning("Presence check failed: %s", exc)
        return set()


# ─────────────────────────────────────────────────────────────────────────────
# Typing Indicator
# ─────────────────────────────────────────────────────────────────────────────

def _typing_key(group_id: int, user_id: int) -> str:
    return f"typing:{group_id}:{user_id}"


async def set_typing(group_id: int, user_id: int, is_typing: bool) -> None:
    """Set or clear the typing indicator for a user in a group."""
    redis = await get_redis()
    if not redis:
        return
    try:
        key = _typing_key(group_id, user_id)
        if is_typing:
            await redis.setex(key, TYPING_TTL, "1")
        else:
            await redis.delete(key)
    except Exception as exc:
        logger.warning("Typing set failed: %s", exc)


async def get_typing_user_ids(group_id: int, member_ids: list[int]) -> list[int]:
    """Return user_ids that are currently typing in this group."""
    redis = await get_redis()
    if not redis or not member_ids:
        return []
    try:
        keys = [_typing_key(group_id, uid) for uid in member_ids]
        results = await redis.mget(keys)
        return [uid for uid, val in zip(member_ids, results) if val is not None]
    except Exception as exc:
        logger.warning("Typing check failed: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Rate Limiting
# ─────────────────────────────────────────────────────────────────────────────

async def check_rate_limit(key: str, max_count: int, window_seconds: int) -> bool:
    """
    Sliding window rate limiter.
    Returns True if request is allowed, False if rate-limited.
    """
    redis = await get_redis()
    if not redis:
        # If Redis is unavailable, allow all (fail open for availability)
        return True
    try:
        now = time.time()
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, "-inf", now - window_seconds)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds + 1)
        results = await pipe.execute()
        count = results[1]
        return count < max_count
    except Exception as exc:
        logger.warning("Rate limit check failed: %s", exc)
        return True  # fail open


async def check_message_rate_limit(user_id: int) -> bool:
    """Check if user can send a message (20 msgs / 10 seconds)."""
    key = f"ratelimit:msg:{user_id}"
    return await check_rate_limit(key, RATE_LIMIT_MESSAGES, RATE_LIMIT_WINDOW)


async def check_group_create_rate_limit(user_id: int) -> bool:
    """Check if user can create a group (5 / 60 seconds)."""
    key = f"ratelimit:gcreate:{user_id}"
    return await check_rate_limit(key, RATE_LIMIT_GROUP_CREATE, 60)
