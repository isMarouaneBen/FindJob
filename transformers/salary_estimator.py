"""
Moroccan salary estimator.

Provides a fallback when the source does not expose a salary range. The
estimates are monthly gross averages in MAD (dirhams) derived from local
market references (ReKrute salary barometer, Rekrute/Michael-Page 2024-2025
surveys) and are intentionally wide to reflect the dispersion observed in
practice.

Lookup is keyed by normalized role keywords found in the job title, then
adjusted by seniority (experience years) and education level.
"""

from __future__ import annotations

import re
import unicodedata

# Monthly gross salary brackets in MAD, indexed by role keyword (lowercased,
# no accents). Order matters: the first matching keyword wins.
ROLE_SALARY_MAD: list[tuple[str, tuple[int, int]]] = [
    # Internships & alternance must come first — otherwise "Stage marketing"
    # would match "marketing" before "stage".
    ("stagiaire",                   (2500,  6000)),
    ("internship",                  (2500,  6000)),
    ("stage",                       (2500,  6000)),
    ("alternance",                  (4000,  8000)),
    ("architecte data",            (28000, 45000)),
    ("data architect",              (28000, 45000)),
    ("architecte",                  (25000, 40000)),
    ("data governance",             (22000, 38000)),
    ("data scientist",              (18000, 35000)),
    ("data engineer",               (17000, 32000)),
    ("machine learning",            (18000, 35000)),
    ("ml engineer",                 (18000, 35000)),
    ("data analyst",                (12000, 25000)),
    ("business analyst",            (13000, 26000)),
    ("business intelligence",       (14000, 28000)),
    ("bi developer",                (14000, 28000)),
    ("devops",                      (18000, 35000)),
    ("sre",                         (20000, 38000)),
    ("cloud",                       (18000, 35000)),
    ("cybersecur",                  (18000, 38000)),
    ("securite",                    (16000, 32000)),
    ("full stack",                  (14000, 28000)),
    ("fullstack",                   (14000, 28000)),
    ("back end",                    (14000, 28000)),
    ("backend",                     (14000, 28000)),
    ("front end",                   (13000, 26000)),
    ("frontend",                    (13000, 26000)),
    ("mobile",                      (14000, 28000)),
    ("developpeur",                 (12000, 25000)),
    ("developer",                   (12000, 25000)),
    ("ingenieur logiciel",          (14000, 28000)),
    ("software engineer",           (14000, 28000)),
    ("administrateur systeme",      (12000, 22000)),
    ("administrateur",              (11000, 22000)),
    ("datacenter",                  (14000, 28000)),
    ("reseau",                      (12000, 24000)),
    ("chef de projet",              (20000, 38000)),
    ("project manager",             (20000, 38000)),
    ("product owner",               (18000, 32000)),
    ("product manager",             (20000, 38000)),
    ("scrum master",                (18000, 32000)),
    ("consultant",                  (15000, 30000)),
    ("responsable",                 (18000, 35000)),
    ("manager",                     (20000, 40000)),
    ("directeur",                   (35000, 70000)),
    ("comptab",                     (8000,  18000)),
    ("finance",                     (12000, 28000)),
    ("commercial",                  (10000, 22000)),
    ("marketing",                   (10000, 22000)),
    ("rh",                          (10000, 22000)),
    ("ressources humaines",         (10000, 22000)),
    ("qualite",                     (10000, 20000)),
    ("support",                     (7000,  14000)),
    ("technicien",                  (6000,  12000)),
]

# Default bracket when nothing matches (entry-level qualified position).
DEFAULT_RANGE_MAD: tuple[int, int] = (10000, 22000)

# Rough EUR → MAD conversion for cross-country comparison display.
EUR_TO_MAD = 10.9

# Brackets EUR (France, brut annuel). Repères marché Tech FR 2024-2025
# (Apec, Hays, Robert Half). Ils sont volontairement larges pour absorber
# les écarts Paris / régions et junior / senior.
ROLE_SALARY_EUR: list[tuple[str, tuple[int, int]]] = [
    ("stagiaire",                  ( 6000,  12000)),  # gratification annualisée
    ("internship",                 ( 6000,  12000)),
    ("stage",                      ( 6000,  12000)),
    ("alternance",                 (10000,  22000)),
    ("architecte data",            (65000, 100000)),
    ("data architect",             (65000, 100000)),
    ("architecte",                 (60000,  95000)),
    ("data governance",            (55000,  85000)),
    ("data scientist",             (45000,  75000)),
    ("data engineer",              (45000,  72000)),
    ("machine learning",           (50000,  80000)),
    ("ml engineer",                (50000,  80000)),
    ("data analyst",               (38000,  55000)),
    ("business analyst",           (40000,  60000)),
    ("business intelligence",      (42000,  65000)),
    ("bi developer",               (42000,  65000)),
    ("devops",                     (48000,  75000)),
    ("sre",                        (55000,  85000)),
    ("cloud",                      (50000,  80000)),
    ("cybersecur",                 (50000,  80000)),
    ("securite",                   (45000,  72000)),
    ("full stack",                 (42000,  65000)),
    ("fullstack",                  (42000,  65000)),
    ("back end",                   (42000,  65000)),
    ("backend",                    (42000,  65000)),
    ("front end",                  (40000,  60000)),
    ("frontend",                   (40000,  60000)),
    ("mobile",                     (42000,  65000)),
    ("developpeur",                (38000,  60000)),
    ("developer",                  (38000,  60000)),
    ("ingenieur logiciel",         (45000,  70000)),
    ("software engineer",          (45000,  70000)),
    ("administrateur systeme",     (38000,  55000)),
    ("administrateur",             (35000,  55000)),
    ("datacenter",                 (40000,  60000)),
    ("reseau",                     (38000,  55000)),
    ("chef de projet",             (50000,  80000)),
    ("project manager",            (50000,  80000)),
    ("product owner",              (48000,  72000)),
    ("product manager",            (55000,  85000)),
    ("scrum master",               (50000,  75000)),
    ("consultant",                 (42000,  68000)),
    ("responsable",                (50000,  80000)),
    ("manager",                    (55000,  85000)),
    ("directeur",                  (80000, 140000)),
]
DEFAULT_RANGE_EUR: tuple[int, int] = (35000, 55000)


def _norm(text: str | None) -> str:
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )


def _seniority_multiplier(experience_years: int | None, diplome_niveau: str | None) -> float:
    """Scale the base bracket by experience and education."""
    mult = 1.0
    if experience_years is not None:
        if experience_years >= 10:
            mult *= 1.35
        elif experience_years >= 7:
            mult *= 1.20
        elif experience_years >= 4:
            mult *= 1.05
        elif experience_years <= 1:
            mult *= 0.85
    if diplome_niveau:
        lvl = _norm(diplome_niveau)
        if "bac+5" in lvl or "ingenieur" in lvl or "master" in lvl or "doctorat" in lvl:
            mult *= 1.05
        elif "bac+3" in lvl or "licence" in lvl:
            mult *= 0.90
        elif "bac+2" in lvl:
            mult *= 0.80
    return mult


def estimate_salary_mad(
    poste: str | None = None,
    titre: str | None = None,
    experience_years: int | None = None,
    diplome_niveau: str | None = None,
) -> dict[str, object]:
    """
    Return an estimated monthly MAD salary bracket. The result is always
    populated — it falls back to a default bracket when no keyword matches.

    The returned dict is meant to be merged into a job record; the
    `source_salaire` key is always "estimation_marche_maroc" so downstream
    consumers can tell estimates apart from real figures.
    """
    haystack = _norm(f"{poste or ''} {titre or ''}")
    base: tuple[int, int] | None = None
    matched_key: str | None = None
    for key, rng in ROLE_SALARY_MAD:
        if key in haystack:
            base = rng
            matched_key = key
            break
    if base is None:
        base = DEFAULT_RANGE_MAD

    mult = _seniority_multiplier(experience_years, diplome_niveau)
    lo = int(round(base[0] * mult / 500.0)) * 500
    hi = int(round(base[1] * mult / 500.0)) * 500
    return {
        "salaire_min": lo,
        "salaire_max": hi,
        "devise": "MAD",
        "source_salaire": "estimation_marche_maroc",
        "salaire_match": matched_key,
    }


def estimate_salary_eur(
    poste: str | None = None,
    titre: str | None = None,
    experience_years: int | None = None,
    diplome_niveau: str | None = None,
) -> dict[str, object]:
    """Pendant France de `estimate_salary_mad` : renvoie EUR / brut annuel."""
    haystack = _norm(f"{poste or ''} {titre or ''}")
    base: tuple[int, int] | None = None
    matched_key: str | None = None
    for key, rng in ROLE_SALARY_EUR:
        if key in haystack:
            base = rng
            matched_key = key
            break
    if base is None:
        base = DEFAULT_RANGE_EUR
    mult = _seniority_multiplier(experience_years, diplome_niveau)
    lo = int(round(base[0] * mult / 1000.0)) * 1000
    hi = int(round(base[1] * mult / 1000.0)) * 1000
    return {
        "salaire_min": lo,
        "salaire_max": hi,
        "devise": "EUR",
        "source_salaire": "estimation_marche_france",
        "salaire_match": matched_key,
    }


# --------------------------------------------------------------------------- #
# Parsing salary out of free-text descriptions
# --------------------------------------------------------------------------- #

_SALARY_TEXT_PATTERNS = [
    re.compile(
        r"(?:salaire|r[ée]mun[ée]ration|package)\s*[:\-]?\s*"
        r"(?:entre\s+)?(\d[\d\s.,]*)\s*(?:[àa\-]|to|et)\s*(\d[\d\s.,]*)\s*(MAD|DH|dirham|€|EUR|USD|\$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d[\d\s.,]{2,})\s*[-àa]\s*(\d[\d\s.,]{2,})\s*(MAD|DH|dirham|€|EUR)",
        re.IGNORECASE,
    ),
]


def _to_number(raw: str) -> float | None:
    cleaned = raw.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_salary_from_text(text: str | None) -> dict[str, object] | None:
    """Extract an explicit salary range from a description, if present."""
    if not text:
        return None
    for pat in _SALARY_TEXT_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        lo = _to_number(m.group(1))
        hi = _to_number(m.group(2))
        if lo is None or hi is None or lo <= 0 or hi <= 0:
            continue
        currency = m.group(3).upper()
        devise = "MAD" if currency in ("MAD", "DH", "DIRHAM") else ("EUR" if currency in ("€", "EUR") else currency)
        # sanity: reject ranges that look like years or phone numbers
        if hi < lo:
            lo, hi = hi, lo
        if hi > 10_000_000 or lo < 500:
            continue
        return {
            "salaire_min": lo,
            "salaire_max": hi,
            "devise": devise,
            "source_salaire": "description",
            "salaire_match": None,
        }
    return None
