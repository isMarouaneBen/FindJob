"""
FastAPI application entrypoint.

Startup tasks:
  1. Configure logging.
  2. Init Postgres engine + ensure pgvector extension and embedding column.
  3. Connect Redis (best-effort).
  4. Start Kafka producer (best-effort).
  5. Ensure MinIO buckets exist.
  6. Load the embedding model into memory.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, init_engine
from app.services import (
    embedding,
    kafka_producer,
    minio_client,
    redis_client,
    tech_extractor,
    tech_vocab,
)

logger = logging.getLogger(__name__)


async def _init_pgvector() -> None:
    engine = init_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text(f"""
            ALTER TABLE analytics.fact_offer
            ADD COLUMN IF NOT EXISTS embedding vector({settings.EMBEDDING_DIM})
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_fact_offer_embedding
            ON analytics.fact_offer
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
    logger.info("pgvector extension + index ready")


async def _init_auth_schema() -> None:
    """Idempotent bootstrap of the auth schema (mirrors postgres-init/04-auth.sql)
    so the table also exists in DBs that were initialised before this commit."""
    engine = init_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auth.users (
                user_id       BIGSERIAL    PRIMARY KEY,
                email         TEXT         NOT NULL UNIQUE,
                full_name     TEXT         NOT NULL DEFAULT '',
                password_hash TEXT,
                provider      TEXT         NOT NULL DEFAULT 'local',
                google_sub    TEXT         UNIQUE,
                picture       TEXT,
                created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
                last_login_at TIMESTAMPTZ,
                CONSTRAINT chk_users_provider CHECK (provider IN ('local','google')),
                CONSTRAINT chk_users_password CHECK (
                    (provider='local'  AND password_hash IS NOT NULL)
                 OR (provider='google' AND google_sub    IS NOT NULL)
                )
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(LOWER(email))"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_users_google_sub ON auth.users(google_sub) "
            "WHERE google_sub IS NOT NULL"
        ))
    logger.info("auth schema ready")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    await _init_pgvector()
    await _init_auth_schema()
    await tech_vocab.load_from_db()
    await tech_extractor.load_from_db()
    await redis_client.init_redis()
    await kafka_producer.init_producer()
    try:
        await minio_client.ensure_buckets()
    except Exception as e:  # noqa: BLE001
        logger.warning("MinIO unreachable at startup (%s); CV uploads will fail", e)

    # Pre-load the embedding model so the first request isn't slow.
    try:
        embedding.load_model()
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load embedding model: %s", e)

    logger.info("Application ready")
    yield

    logger.info("Shutting down")
    await kafka_producer.close_producer()
    await redis_client.close_redis()
    await dispose_engine()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Job recommendation engine — pgvector + hybrid scoring",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }
