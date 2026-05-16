"""
Application configuration.

Centralizes settings for Postgres, Redis, Kafka, MinIO and the embedding model.
Values are sourced from environment variables (or .env) and validated by
pydantic-settings.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- App ----
    APP_NAME: str = "Job Intelligence Platform API"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["*"])
    LOG_LEVEL: str = "INFO"

    # ---- Postgres ----
    DATABASE_URL: str = "postgresql+asyncpg://datauser:datapass@postgres:5432/job_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_SCHEMA: str = "analytics"

    # ---- Embedding model ----
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384
    EMBEDDING_DEVICE: str = "cpu"

    # ---- Redis (cache + rate-limit + idempotency) ----
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_CACHE_TTL_SECONDS: int = 300

    # ---- Kafka (async events: cv.uploaded, profile.embed.requested...) ----
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_CV_UPLOADED: str = "cv.uploaded"
    KAFKA_TOPIC_PROFILE_EMBED: str = "profile.embed.requested"
    KAFKA_CONSUMER_GROUP: str = "platform-api"

    # ---- MinIO (CV blob storage) ----
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_CV: str = "cv-uploads"
    MINIO_PRESIGN_EXPIRY_SECONDS: int = 3600

    # ---- Matching / Recommendation ----
    RECO_DEFAULT_TOP_K: int = 20
    RECO_MAX_TOP_K: int = 100
    RECO_VECTOR_CANDIDATES: int = 200  # ANN pre-filter pool before re-rank
    RECO_WEIGHT_VECTOR: float = 0.55
    RECO_WEIGHT_TECH_OVERLAP: float = 0.20
    RECO_WEIGHT_SENIORITY: float = 0.08
    RECO_WEIGHT_CONTRACT: float = 0.05
    RECO_WEIGHT_LOCATION: float = 0.05
    RECO_WEIGHT_REMOTE: float = 0.04
    RECO_WEIGHT_LANGUAGE: float = 0.03


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
