"""
Kafka consumer: cv.uploaded → parse CV → cache parsed profile in Redis.

Runs as a standalone process (see Dockerfile.worker).
Pulls the CV bytes from MinIO, runs the parser, and stores the resulting
ProfilePayload in Redis under `cv:profile:<cv_id>` so subsequent
/recommendations/from-cv calls are fast.
"""
from __future__ import annotations

import asyncio
import json
import logging
import signal

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.core.logging import configure_logging
from app.services import embedding, tech_extractor, tech_vocab
from app.services.cv_parser import parse_cv
from app.services.minio_client import get_object
from app.services.redis_client import init_redis, get_redis

logger = logging.getLogger(__name__)


async def handle_message(payload: dict) -> None:
    cv_id = payload.get("cv_id")
    bucket = payload.get("bucket") or settings.MINIO_BUCKET_CV
    key = payload.get("object_key")
    filename = payload.get("filename") or key
    if not cv_id or not key:
        logger.warning("Skipping malformed message: %s", payload)
        return

    try:
        data = await get_object(bucket, key)
        profile = parse_cv(filename or key, data)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to parse CV %s: %s", cv_id, e)
        return

    # Pre-compute the profile embedding so /recommendations/from-cv can skip
    # both the PDF parse and the model encode on subsequent requests.
    try:
        vec = await embedding.embed_one(profile.embedding_text())
    except Exception as e:  # noqa: BLE001
        logger.warning("Embedding failed for cv %s: %s", cv_id, e)
        vec = None

    redis = get_redis()
    if redis is None:
        return
    try:
        await redis.set(
            f"cv:profile:{cv_id}", profile.model_dump_json(), ex=24 * 3600
        )
        if vec is not None:
            await redis.set(
                f"cv:embedding:{cv_id}",
                json.dumps(vec),
                ex=24 * 3600,
            )
        logger.info(
            "Parsed CV %s (tech=%d, langs=%d, years=%d, embedded=%s)",
            cv_id, len(profile.tech_stack), len(profile.langues),
            profile.annees_experience, vec is not None,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to cache parsed profile %s: %s", cv_id, e)


async def main() -> None:
    configure_logging()
    await init_redis()
    await tech_vocab.load_from_db()
    await tech_extractor.load_from_db()
    # Pre-load the embedding model so the first message isn't slow.
    try:
        embedding.load_model()
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not pre-load embedding model: %s", e)

    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_CV_UPLOADED,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    logger.info("CV consumer started on topic %s", settings.KAFKA_TOPIC_CV_UPLOADED)

    stop = asyncio.Event()

    def _stop(*_):
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass  # Windows

    try:
        async for msg in consumer:
            if stop.is_set():
                break
            await handle_message(msg.value)
    finally:
        await consumer.stop()
        logger.info("CV consumer stopped")


if __name__ == "__main__":
    asyncio.run(main())
