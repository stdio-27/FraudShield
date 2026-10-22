"""
Redis helpers that degrade gracefully.

Redis is an optimisation, not a dependency: if it is unreachable, cached reads
fall through to the database and rate limiting falls back to an in-process
counter instead of turning every request into a 500.
"""

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None
_available = False
_last_probe = 0.0
_PROBE_INTERVAL = 15.0

# In-process fallback limiter: key -> (count, window_reset_epoch)
_local_counters: dict[str, tuple[int, float]] = {}
_LOCAL_COUNTER_MAX_KEYS = 10_000


async def init(url: str) -> None:
    global _client, _available
    _client = redis.from_url(
        url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    )
    try:
        await _client.ping()
        _available = True
        logger.info("Redis connection established.")
    except Exception as exc:
        _available = False
        logger.warning("Redis unavailable at startup (%s); continuing without cache.", exc)


async def close() -> None:
    global _client, _available
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
    _client = None
    _available = False


def is_available() -> bool:
    return _available


def _mark_failure(exc: Exception) -> None:
    global _available
    if _available:
        logger.warning("Redis error (%s); falling back to uncached operation.", exc)
    _available = False


async def _reconnect_probe() -> None:
    """Recovery check so a transient outage does not disable Redis forever (at most every 15 s)."""
    global _available, _last_probe
    if _client is None or _available:
        return
    now = time.monotonic()
    if now - _last_probe < _PROBE_INTERVAL:
        return
    _last_probe = now
    try:
        await _client.ping()
        _available = True
        logger.info("Redis connection recovered.")
    except Exception:
        pass


async def get_json(key: str) -> Any:
    if _client is None:
        return None
    if not _available:
        await _reconnect_probe()
        if not _available:
            return None
    try:
        raw = await _client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        _mark_failure(exc)
        return None


async def set_json(key: str, value: Any, ttl: int) -> None:
    if _client is None or not _available:
        return
    try:
        await _client.set(key, json.dumps(value), ex=ttl)
    except Exception as exc:
        _mark_failure(exc)


async def delete(*keys: str) -> None:
    if _client is None or not _available:
        return
    try:
        await _client.delete(*keys)
    except Exception as exc:
        _mark_failure(exc)


async def cached(key: str, ttl: int, builder: Callable[[], Awaitable[Any]]) -> Any:
    """
    Return the cached value for ``key`` or build it.  A short-lived Redis lock
    makes concurrent cache misses wait for one builder instead of stampeding
    the database.
    """
    value = await get_json(key)
    if value is not None:
        return value

    lock_key = f"lock:{key}"
    got_lock = False
    if _client is not None and _available:
        try:
            got_lock = bool(await _client.set(lock_key, "1", nx=True, ex=10))
        except Exception as exc:
            _mark_failure(exc)

        if not got_lock and _available:
            for _ in range(10):
                await asyncio.sleep(0.2)
                value = await get_json(key)
                if value is not None:
                    return value

    try:
        result = await builder()
        await set_json(key, result, ttl)
        return result
    finally:
        if got_lock:
            await delete(lock_key)


async def rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Fixed-window counter.  Returns True when the call is allowed."""
    full_key = f"rl:{key}"

    if _client is not None and _available:
        try:
            count = await _client.incr(full_key)
            if count == 1:
                await _client.expire(full_key, window_seconds)
            return count <= limit
        except Exception as exc:
            _mark_failure(exc)

    now = time.monotonic()
    if len(_local_counters) > _LOCAL_COUNTER_MAX_KEYS:
        for k in [k for k, (_, reset) in _local_counters.items() if reset <= now]:
            _local_counters.pop(k, None)
    count, reset = _local_counters.get(full_key, (0, now + window_seconds))
    if reset <= now:
        count, reset = 0, now + window_seconds
    count += 1
    _local_counters[full_key] = (count, reset)
    return count <= limit


async def rate_limit_reset(key: str) -> None:
    full_key = f"rl:{key}"
    _local_counters.pop(full_key, None)
    await delete(full_key)
