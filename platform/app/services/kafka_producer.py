"""
Async Kafka producer using aiokafka.

Used to fan out async work without blocking the request:
  - cv.uploaded → CV parsing worker picks up the object_key, extracts text,
    embeds, and stores parsed profile back to Postgres.
  - profile.embed.requested → re-embed a stored profile.

If Kafka is unreachable at startup the producer becomes a no-op; the API
remains usable for synchronous matching against pre-computed offer embeddings.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.core.config import settings

logger = logging.getLogger(__name__)

_producer: Optional[AIOKafkaProducer] = None
_enabled: bool = False


async def init_producer() -> None:
    global _producer, _enabled
    if _producer is not None:
        return
    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            enable_idempotence=True,
        )
        await _producer.start()
        _enabled = True
        logger.info("Kafka producer started (%s)", settings.KAFKA_BOOTSTRAP_SERVERS)
    except (KafkaError, OSError) as e:
        _producer = None
        _enabled = False
        logger.warning("Kafka unreachable (%s); events disabled", e)


async def close_producer() -> None:
    global _producer, _enabled
    if _producer is not None:
        try:
            await _producer.stop()
        finally:
            _producer = None
            _enabled = False


async def publish(topic: str, payload: Dict[str, Any], key: Optional[str] = None) -> bool:
    if not _enabled or _producer is None:
        logger.debug("Kafka disabled; dropping event topic=%s", topic)
        return False
    try:
        await _producer.send_and_wait(
            topic, value=payload, key=key.encode("utf-8") if key else None
        )
        return True
    except KafkaError as e:
        logger.error("Kafka publish failed topic=%s err=%s", topic, e)
        return False
