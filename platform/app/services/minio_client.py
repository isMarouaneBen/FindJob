"""
MinIO client for CV blob storage.

Buckets are created on startup. Uploads happen synchronously via the official
`minio` SDK, wrapped in `asyncio.to_thread` so they don't block the event loop.
"""
from __future__ import annotations

import asyncio
import io
import logging
from datetime import timedelta
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[Minio] = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def _ensure_bucket_sync(bucket: str) -> None:
    client = get_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created MinIO bucket %s", bucket)


async def ensure_buckets() -> None:
    await asyncio.to_thread(_ensure_bucket_sync, settings.MINIO_BUCKET_CV)


def _put_sync(bucket: str, key: str, data: bytes, content_type: str) -> None:
    client = get_client()
    client.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


async def put_object(bucket: str, key: str, data: bytes, content_type: str) -> None:
    await asyncio.to_thread(_put_sync, bucket, key, data, content_type)


def _get_sync(bucket: str, key: str) -> bytes:
    client = get_client()
    resp = client.get_object(bucket, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


async def get_object(bucket: str, key: str) -> bytes:
    return await asyncio.to_thread(_get_sync, bucket, key)


def _presign_sync(bucket: str, key: str, expires: int) -> str:
    client = get_client()
    return client.presigned_get_object(bucket, key, expires=timedelta(seconds=expires))


async def presigned_url(
    bucket: str, key: str, expires: int = settings.MINIO_PRESIGN_EXPIRY_SECONDS
) -> str:
    return await asyncio.to_thread(_presign_sync, bucket, key, expires)
