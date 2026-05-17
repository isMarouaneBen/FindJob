"""
Internal/admin endpoints — meant to be called by Airflow, cron, or a manual
operator. Protected by a shared secret header (X-Admin-Token) since these
operations can be expensive.

  POST /admin/embed-offers   — embed every fact_offer row that has no embedding,
                                then invalidate the reco cache.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.services import embedding
from app.services.redis_client import get_redis

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)


def _require_admin(x_admin_token: Optional[str] = Header(None)) -> None:
    if not settings.ADMIN_TOKEN or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid or missing X-Admin-Token")


SELECT_PENDING_SQL = """
SELECT
    f.offer_id,
    f.poste,
    f.titre_original,
    f.description_brute,
    soc.societe_nom,
    v.ville_nom,
    p.pays_nom,
    m.metier_libelle,
    sen.seniorite_libelle,
    c.contrat_libelle,
    t.teletravail_libelle,
    f.competences,
    f.missions,
    f.langues,
    COALESCE((
        SELECT array_agg(dt.tech_nom)
          FROM analytics.bridge_offer_technologie b
          JOIN analytics.dim_technologie dt ON dt.tech_id = b.tech_id
         WHERE b.offer_id = f.offer_id AND dt.tech_id <> 0
    ), '{}'::text[]) AS technologies
FROM analytics.fact_offer f
JOIN analytics.dim_societe        soc ON soc.societe_id   = f.societe_id
JOIN analytics.dim_ville          v   ON v.ville_id       = f.ville_id
JOIN analytics.dim_pays           p   ON p.pays_id        = f.pays_id
JOIN analytics.dim_metier         m   ON m.metier_id      = f.metier_id
JOIN analytics.dim_seniorite      sen ON sen.seniorite_id = f.seniorite_id
JOIN analytics.dim_contrat        c   ON c.contrat_id     = f.contrat_id
JOIN analytics.dim_teletravail    t   ON t.teletravail_id = f.teletravail_id
WHERE f.embedding IS NULL AND NOT f.is_duplicate
ORDER BY f.offer_id
LIMIT :limit
"""


def _build_text(row) -> str:
    """Mirror of scripts/embed_offers_v2.build_text — kept inline so the
    endpoint is independent of the scripts folder."""
    m = row._mapping
    parts: List[str] = []
    title = (m.get("poste") or "").strip()
    if title:
        parts.extend([title] * 3)
    other = (m.get("titre_original") or "").strip()
    if other and other != title:
        parts.append(other)
    for k in ("metier_libelle", "seniorite_libelle", "contrat_libelle",
              "teletravail_libelle", "societe_nom", "ville_nom"):
        v = m.get(k)
        if v and v != "Non spécifié":
            parts.append(str(v))
    for v in (m.get("technologies") or [])[:25]:
        parts.append(str(v))
    for v in (m.get("competences") or [])[:15]:
        parts.append(str(v))
    for v in (m.get("missions") or [])[:10]:
        parts.append(str(v))
    for v in (m.get("langues") or [])[:5]:
        parts.append(str(v))
    desc = (m.get("description_brute") or "").strip()
    if desc:
        parts.append(desc[:3500])
    return " ".join(p.strip() for p in parts if p)[:4000] or "Job offer"


async def _flush_reco_cache() -> int:
    """Drop every reco:* key so new offers show up immediately."""
    redis = get_redis()
    if redis is None:
        return 0
    deleted = 0
    try:
        async for k in redis.scan_iter(match="reco:*", count=500):
            await redis.delete(k)
            deleted += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to flush reco cache: %s", e)
    return deleted


@router.post("/embed-offers", dependencies=[Depends(_require_admin)])
async def embed_pending_offers(
    limit: int = 20_000,
    batch_size: int = 32,
    session: AsyncSession = Depends(get_session),
):
    """Embed every offer without an embedding, in batches.
    Returns: { embedded, batches, cache_invalidated }.
    Idempotent — safe to call after every scrape.
    """
    rows = (await session.execute(text(SELECT_PENDING_SQL), {"limit": limit})).all()
    if not rows:
        flushed = await _flush_reco_cache()
        return {"embedded": 0, "batches": 0, "cache_invalidated": flushed,
                "message": "Nothing to embed."}

    logger.info("admin/embed-offers: %d offers pending", len(rows))

    total = 0
    batches = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        texts = [_build_text(r) for r in chunk]
        vectors = await embedding.embed_texts(texts)
        for r, v in zip(chunk, vectors):
            literal = "[" + ",".join(f"{x:.6f}" for x in v) + "]"
            await session.execute(
                text("UPDATE analytics.fact_offer "
                     "SET embedding = CAST(:vec AS analytics.vector) "
                     "WHERE offer_id = :id"),
                {"vec": literal, "id": r._mapping["offer_id"]},
            )
        await session.commit()
        total += len(chunk)
        batches += 1
        logger.info("admin/embed-offers: %d / %d", total, len(rows))

    flushed = await _flush_reco_cache()
    return {"embedded": total, "batches": batches, "cache_invalidated": flushed}
