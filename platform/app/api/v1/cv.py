"""
CV upload endpoint.

Flow:
  1. Validate file extension and size.
  2. Stream the bytes to MinIO under `cv-uploads/<uuid>.<ext>`.
  3. Publish a `cv.uploaded` Kafka event so a worker can parse it
     asynchronously and store the extracted profile (future use).
  4. Return the cv_id; callers can immediately POST it to
     /recommendations/from-cv/{cv_id} for matching.
"""
from __future__ import annotations

import uuid
from typing import Tuple

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.profile import CVUploadResponse
from app.services import kafka_producer, minio_client

router = APIRouter(prefix="/cv", tags=["CV"])

ALLOWED_EXT = {"pdf", "docx", "txt"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _split_ext(filename: str) -> Tuple[str, str]:
    if "." not in filename:
        return filename, ""
    base, _, ext = filename.rpartition(".")
    return base, ext.lower()


@router.post("/upload", response_model=CVUploadResponse, status_code=201)
async def upload_cv(file: UploadFile = File(...)):
    _, ext = _split_ext(file.filename or "")
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type .{ext}; allowed: {sorted(ALLOWED_EXT)}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (>5MB)")

    cv_id = uuid.uuid4().hex
    key = f"{cv_id}.{ext}"

    await minio_client.put_object(
        settings.MINIO_BUCKET_CV,
        key,
        data,
        content_type=file.content_type or "application/octet-stream",
    )

    await kafka_producer.publish(
        settings.KAFKA_TOPIC_CV_UPLOADED,
        {
            "cv_id": cv_id,
            "object_key": key,
            "bucket": settings.MINIO_BUCKET_CV,
            "filename": file.filename,
            "size": len(data),
        },
        key=cv_id,
    )

    return CVUploadResponse(
        cv_id=cv_id,
        object_key=key,
        bucket=settings.MINIO_BUCKET_CV,
    )
