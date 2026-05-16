"""
Recommendation endpoints.

POST /recommendations            — form-based profile, synchronous matching
POST /recommendations/from-cv    — match against a previously uploaded CV

The from-cv flow prefers the parsed profile + embedding cached by the Kafka
worker (cv:profile:{id} and cv:embedding:{id}). It falls back to fetching
the CV from MinIO and parsing it inline if the cache is cold.
"""
import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.schemas.profile import ProfilePayload
from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.services import matching
from app.services.cv_parser import parse_cv
from app.services.minio_client import get_object
from app.services.redis_client import cache_get, cache_set, get_redis

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])
logger = logging.getLogger(__name__)


def _cache_key(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return "reco:" + hashlib.sha256(blob).hexdigest()


@router.post("", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    session: AsyncSession = Depends(get_session),
):
    key = _cache_key(request.model_dump())
    cached = await cache_get(key)
    if cached:
        return RecommendationResponse.model_validate_json(cached)

    items = await matching.recommend(session, request)
    response = RecommendationResponse(count=len(items), items=items)
    await cache_set(key, response.model_dump_json())
    return response


async def _load_cv_profile(cv_id: str) -> tuple[ProfilePayload, list[float] | None]:
    """Return (profile, embedding-or-None), preferring the Kafka-warmed cache."""
    redis = get_redis()
    if redis is not None:
        try:
            cached_profile = await redis.get(f"cv:profile:{cv_id}")
            cached_vec_raw = await redis.get(f"cv:embedding:{cv_id}")
        except Exception as e:  # noqa: BLE001
            logger.debug("Redis lookup failed for cv %s: %s", cv_id, e)
            cached_profile = cached_vec_raw = None
        if cached_profile:
            profile = ProfilePayload.model_validate_json(cached_profile)
            vec = json.loads(cached_vec_raw) if cached_vec_raw else None
            logger.info("CV %s served from cache (embedding=%s)",
                        cv_id, vec is not None)
            return profile, vec

    # Cache miss: fetch the raw object and parse inline. Try each known
    # extension since the upload endpoint stored the original suffix.
    last_err: Exception | None = None
    for ext in ("pdf", "docx", "txt"):
        try:
            data = await get_object(settings.MINIO_BUCKET_CV, f"{cv_id}.{ext}")
            profile = parse_cv(f"{cv_id}.{ext}", data)
            # Warm the cache for next time.
            if redis is not None:
                try:
                    await redis.set(
                        f"cv:profile:{cv_id}",
                        profile.model_dump_json(),
                        ex=24 * 3600,
                    )
                except Exception:  # noqa: BLE001
                    pass
            return profile, None
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue

    raise HTTPException(status_code=404, detail=f"CV {cv_id} not found ({last_err})")


@router.post("/from-cv/{cv_id}", response_model=RecommendationResponse)
async def recommend_from_cv(
    cv_id: str,
    top_k: int = 20,
    session: AsyncSession = Depends(get_session),
):
    profile, precomputed = await _load_cv_profile(cv_id)
    items = await matching.recommend_from_payload(
        session, profile, top_k=top_k, precomputed_embedding=precomputed
    )
    return RecommendationResponse(count=len(items), items=items)
