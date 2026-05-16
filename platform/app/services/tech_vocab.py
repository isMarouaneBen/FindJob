"""
Canonical tech vocabulary loaded from analytics.dim_technologie.

The set is loaded once into module-level state and reused by the CV parser
so that `matched_technologies` aligns with the same names used to label
offers (avoiding false negatives where, say, the offer says "PostgreSQL"
and the CV parser only knows "postgres").

Falls back to a small hardcoded set if the DB is unreachable at startup.
"""
from __future__ import annotations

import logging
from typing import Set

from sqlalchemy import text

from app.db.session import get_engine

logger = logging.getLogger(__name__)

_FALLBACK: Set[str] = {
    "python", "java", "javascript", "typescript", "go", "rust", "scala",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "spark", "kafka", "airflow", "dbt", "snowflake", "bigquery",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
    "react", "vue", "angular", "fastapi", "django", "flask",
    "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow",
    "power bi", "tableau",
}

_vocab: Set[str] = set(_FALLBACK)
_loaded: bool = False


def current() -> Set[str]:
    return _vocab


def is_loaded() -> bool:
    return _loaded


async def load_from_db() -> Set[str]:
    """Refresh the in-process vocabulary from analytics.dim_technologie."""
    global _vocab, _loaded
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT tech_nom FROM analytics.dim_technologie WHERE tech_id <> 0")
            )
            names = {row[0].strip().lower() for row in result if row[0]}
        if names:
            _vocab = names
            _loaded = True
            logger.info("Loaded %d technologies from dim_technologie", len(_vocab))
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not load dim_technologie vocab (%s); using fallback", e)
        _vocab = set(_FALLBACK)
        _loaded = False
    return _vocab
