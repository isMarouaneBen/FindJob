"""
Canonical technology extractor.

Builds a regex over (canonical_name + aliases) for every entry in
analytics.dim_technologie. Used by:
  • CV parser  → populates ProfilePayload.tech_stack
  • Matching   → enriches each offer's tech set from description_brute and
                 the free-text competences[] array (in addition to the
                 bridge table which only has tags for ~33% of offers).

The same canonical names are returned on both sides, so Jaccard overlap
finally has the right denominators.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Optional, Set

from sqlalchemy import text as sql_text

from app.db.session import get_engine

logger = logging.getLogger(__name__)

# Manual alias map: alias (lowercase) → canonical tech_nom (matched lower).
# Add aliases as you spot them in CVs/offers.
_ALIASES: Dict[str, str] = {
    # Programming
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "golang": "go",
    "node.js": "javascript",
    "nodejs": "javascript",
    "node": "javascript",

    # Databases
    "postgres": "postgresql",
    "psql": "postgresql",
    "mariadb": "mysql",
    "sqlserver": "sql server",
    "ms sql": "sql server",
    "mssql": "sql server",
    "tsql": "sql server",
    "t-sql": "sql server",
    "es": "elasticsearch",
    "elastic": "elasticsearch",

    # Cloud
    "amazon web services": "aws",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",

    # DevOps
    "k8s": "kubernetes",
    "k3s": "kubernetes",
    "gitlab ci": "gitlab",
    "github actions": "ci/cd",
    "cicd": "ci/cd",

    # Data eng / ML
    "apache spark": "spark",
    "pyspark": "spark",
    "apache airflow": "airflow",
    "apache kafka": "kafka",
    "ml": "machine learning",
    "machine-learning": "machine learning",
    "dl": "deep learning",
    "natural language processing": "nlp",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "tf": "tensorflow",
    "pwbi": "power bi",
    "powerbi": "power bi",

    # Misc
    "shell": "bash",
    "shell scripting": "bash",
    "containers": "docker",
    "iac": "terraform",
}


# Compiled (canonical_lower → compiled_regex) plus a master regex that
# captures any term and returns its canonical via a name → canonical map.
_canonical: Set[str] = set()
_pattern: Optional[re.Pattern] = None
_term_to_canonical: Dict[str, str] = {}
_squashed_to_canonical: Dict[str, str] = {}  # "powerbi" → "power bi"


def _escape_for_pattern(term: str) -> str:
    """Build a regex fragment for a canonical tech name.

    Letters within a word are joined by `\\s*` so that PDF letter-spacing
    artifacts like "P o w er BI" still match "power bi". To avoid false
    positives on very short tokens (e.g. "go" matching "G o" inside a name),
    fuzziness is only applied to words of length ≥ 3.

    The anchors `(?<![A-Za-z0-9_+#])` / `(?![A-Za-z0-9_])` keep word
    boundaries strict so "r" doesn't match "rust" and "sql" doesn't match
    "MySQL" (which is its own canonical anyway).
    """
    word_patterns: list[str] = []
    for word in term.split():
        if len(word) >= 3:
            word_patterns.append(r"\s*".join(re.escape(c) for c in word))
        else:
            word_patterns.append(re.escape(word))
    body = r"\s+".join(word_patterns)
    return rf"(?<![A-Za-z0-9_+#]){body}(?![A-Za-z0-9_])"


async def load_from_db() -> None:
    """Refresh the regex from the current contents of dim_technologie."""
    global _canonical, _pattern, _term_to_canonical, _squashed_to_canonical
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            rows = (await conn.execute(
                sql_text("SELECT tech_nom FROM analytics.dim_technologie WHERE tech_id <> 0")
            )).all()
            names = [r[0] for r in rows if r[0]]
    except Exception as e:  # noqa: BLE001
        logger.warning("tech_extractor: could not load dim_technologie (%s)", e)
        names = []

    canonical_lower = {n.strip().lower() for n in names}
    if not canonical_lower:
        # Minimal fallback — keep the parser usable even without DB.
        canonical_lower = {"python", "sql", "java", "aws", "docker", "kubernetes"}

    # Build term → canonical map (canonical + aliases that point to canonical).
    term_map: Dict[str, str] = {n: n for n in canonical_lower}
    for alias, target in _ALIASES.items():
        if target in canonical_lower:
            term_map[alias] = target

    # Compile a single alternation regex. Longer terms first so
    # "machine learning" wins over "machine".
    sorted_terms = sorted(term_map.keys(), key=len, reverse=True)
    pattern = "|".join(_escape_for_pattern(t) for t in sorted_terms)

    _canonical = canonical_lower
    _term_to_canonical = term_map
    _squashed_to_canonical = {
        re.sub(r"\s+", "", term): canon for term, canon in term_map.items()
    }
    _pattern = re.compile(pattern, re.IGNORECASE) if pattern else None
    logger.info(
        "tech_extractor: %d canonical techs, %d aliases, regex length %d",
        len(canonical_lower), len(_ALIASES), len(pattern),
    )


def extract(text: str) -> Set[str]:
    """Return the set of canonical tech names (lowercased) found in `text`."""
    if not text or _pattern is None:
        return set()
    found: Set[str] = set()
    for m in _pattern.finditer(text):
        raw = m.group(0).lower()
        # First try the normalised form ("node   js" → "node js").
        normal = re.sub(r"\s+", " ", raw).strip()
        canon = _term_to_canonical.get(normal)
        if canon is None:
            # PDF letter-spacing fallback: strip all whitespace and look up
            # the squashed form ("p o w er bi" → "powerbi" → "power bi").
            squashed = re.sub(r"\s+", "", raw)
            canon = _squashed_to_canonical.get(squashed)
        if canon:
            found.add(canon)
    return found


def extract_from_many(texts: Iterable[Optional[str]]) -> Set[str]:
    result: Set[str] = set()
    for t in texts:
        if t:
            result.update(extract(t))
    return result


def canonical_names() -> Set[str]:
    return set(_canonical)
