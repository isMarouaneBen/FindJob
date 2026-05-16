#!/usr/bin/env python3
"""
Generate embeddings for every analytics.fact_offer row that doesn't have one
yet. Queries fact_offer directly (so we can filter on the embedding column)
and joins the dimensions needed to build the embedding text.
"""
import asyncio
import logging
import os
import sys

from sentence_transformers import SentenceTransformer
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("embed")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://datauser:datapass@postgres:5432/job_db")
MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
BATCH = int(os.getenv("BATCH_SIZE", "64"))
DEVICE = os.getenv("DEVICE", "cpu")
ONLY_MISSING = os.getenv("ONLY_MISSING", "false").lower() in ("1", "true", "yes")

SELECT_SQL = """
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
WHERE NOT f.is_duplicate
  AND (:only_missing = FALSE OR f.embedding IS NULL)
ORDER BY f.offer_id
"""


def build_text(row) -> str:
    """Embedding text shape, mirrored on the profile side:
    title × 3 → canonical technologies → competences → missions → description body.
    """
    m = row._mapping
    parts: list[str] = []
    title = (m.get("poste") or "").strip()
    if title:
        parts.extend([title] * 3)
    other_title = (m.get("titre_original") or "").strip()
    if other_title and other_title != title:
        parts.append(other_title)
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
    text_ = " ".join(p.strip() for p in parts if p)
    return text_[:4000] or "Job offer"


async def main() -> int:
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)

    @event.listens_for(engine.sync_engine, "connect")
    def _sp(conn, _):
        cur = conn.cursor()
        cur.execute("SET search_path TO analytics, public")
        cur.close()

    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    log.info("Loading model %s ...", MODEL)
    model = SentenceTransformer(MODEL, device=DEVICE)
    log.info("Model loaded (dim=%d)", model.get_sentence_embedding_dimension())

    async with Session() as session:
        rows = (await session.execute(text(SELECT_SQL),
                                      {"only_missing": ONLY_MISSING})).all()

    log.info("Found %d offers to embed", len(rows))
    if not rows:
        await engine.dispose()
        return 0

    total = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        texts = [build_text(r) for r in chunk]
        vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True,
                            show_progress_bar=False)

        async with Session() as session:
            for r, v in zip(chunk, vecs):
                literal = "[" + ",".join(f"{x:.6f}" for x in v.tolist()) + "]"
                await session.execute(
                    text("UPDATE analytics.fact_offer SET embedding = CAST(:vec AS analytics.vector) WHERE offer_id = :id"),
                    {"vec": literal, "id": r._mapping["offer_id"]},
                )
            await session.commit()

        total += len(chunk)
        log.info("Embedded %d / %d", total, len(rows))

    await engine.dispose()
    log.info("Done: %d offers embedded", total)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
