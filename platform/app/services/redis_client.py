"""
Redis async client — cache and (future) rate-limit/idempotency keys.

A single connection pool is exposed via `get_redis()`. Failure to connect
must NOT take the API down; cache helpers degrade to a no-op pattern by
catching exceptions at call sites.
"""
from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None


async def init_redis() -> redis.Redis:
    global _client
    if _client is not None:
        return _client
    _client = redis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )
    try:
        await _client.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL)
    except Exception as e:  # noqa: BLE001
        logger.warning("Redis unreachable (%s); cache disabled", e)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def get_redis() -> Optional[redis.Redis]:
    return _client


async def cache_get(key: str) -> Optional[str]:
    client = get_redis()
    if client is None:
        return None
    try:
        return await client.get(key)
    except Exception as e:  # noqa: BLE001
        logger.debug("cache_get error: %s", e)
        return None


async def cache_set(key: str, value: str, ttl: Optional[int] = None) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.set(key, value, ex=ttl or settings.REDIS_CACHE_TTL_SECONDS)
    except Exception as e:  # noqa: BLE001
        logger.debug("cache_set error: %s", e)
