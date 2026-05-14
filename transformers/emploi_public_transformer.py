"""
Transformer for emploi-public.ma scraped job offers.

Keeps only real job ads (type_annonce == "Annonce") and extracts a
normalized, structured representation from free-text descriptions that
follow many different layouts (OFPPT, CDG, Bank Al-Maghrib, SOREC, ...).

The extraction strategy is deliberately generic: each field has several
fallback patterns and section detectors so the same code can cope with
any new offer format we encounter later.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from enrichment import enrich  # type: ignore
from salary_estimator import estimate_salary_mad, parse_salary_from_text
from skill_normalizer import normalize_skills  # type: ignore

# --------------------------------------------------------------------------- #
# Paths & logging
# --------------------------------------------------------------------------- #

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
INPUT_FILE = BASE_DIR / "data" / "emploi_public_raw.json"
OUTPUT_FILE = BASE_DIR / "data" / "emploi_public_clean.json"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "emploi_public_transformer.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("emploi_public_transformer")


# --------------------------------------------------------------------------- #
# Reference data
# --------------------------------------------------------------------------- #

FRENCH_MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}

MOROCCAN_CITIES = [
    "Casablanca", "Rabat", "Salé", "Sale", "Marrakech", "Fès", "Fes",
    "Tanger", "Agadir", "Meknès", "Meknes", "Oujda", "Kénitra", "Kenitra",
    "Tétouan", "Tetouan", "Safi", "El Jadida", "Nador", "Mohammedia",
    "Laâyoune", "Laayoune", "Dakhla", "Settat", "Beni Mellal", "Khouribga",
    "Errachidia", "Taza", "Essaouira", "Ouarzazate", "Berrechid", "Temara",
]

# Tech keywords (case-insensitive). Kept intentionally broad.
TECH_KEYWORDS = [
    "Python", "Java", "Scala", "R", "SQL", "NoSQL", "PL/SQL", "PowerShell",
    "Bash", "C++", "C#", "JavaScript", "TypeScript", "Go", "Kotlin",
    "Hadoop", "Spark", "Kafka", "Hive", "HBase", "Airflow", "Databricks",
    "Snowflake", "Redshift", "BigQuery", "Teradata",
    "AWS", "Azure", "GCP", "Google Cloud", "OpenStack",
    "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "GitLab",
    "MLOps", "CI/CD",
    "TensorFlow", "PyTorch", "Scikit-Learn", "Keras", "Pandas", "NumPy",
    "NLP", "Machine Learning", "Deep Learning", "Computer Vision",
    "Power BI", "PowerBI", "Tableau", "Qlikview", "QlikView", "Matplotlib",
    "Seaborn", "Looker",
    "MySQL", "PostgreSQL", "Oracle", "MongoDB", "Cassandra", "Redis",
    "Elasticsearch", "SQL Server",
    "Linux", "Unix", "Windows",
    "Hadoop", "ETL", "ELT", "Data Vault", "MDM", "Collibra", "Informatica",
    "Rasa", "Dialogflow", "GPT", "LLM",
    "SAN", "NAS", "VMware", "Hyper-V", "Azure AD", "Active Directory",
]

LANGUAGES = ["français", "francais", "anglais", "arabe", "amazigh", "espagnol", "allemand"]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s,;<>)\"']+", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _normalize_ws(text: str) -> str:
    """Collapse whitespace and trim."""
    return re.sub(r"\s+", " ", text).strip()


def _clean_line(line: str) -> str:
    return _normalize_ws(line.strip(" \t\r\n•▪-*·:;"))


def _split_bullets(block: str) -> list[str]:
    """
    Extract bullet-like items from a text block. Accepts •, ▪, -, *, or
    lines beginning with a digit followed by a dot.
    """
    if not block:
        return []
    # Normalize line breaks inside bullets: a bullet continues until the next
    # bullet marker or a blank line.
    raw = re.split(r"(?:^|\n)\s*(?:[•▪·●■□◦]|[-*])\s+", block)
    items = [r for r in (_clean_line(x) for x in raw) if r]
    # If no bullets detected, split on sentences-per-line.
    if len(items) <= 1:
        items = [_clean_line(ln) for ln in block.splitlines() if _clean_line(ln)]
    # Drop obvious noise
    return [i for i in items if len(i) > 3]


def _section(text: str, start_labels: list[str], stop_labels: list[str]) -> str | None:
    """
    Return the substring between any of `start_labels` and the next
    occurrence of any `stop_labels` (or end of text). Case-insensitive,
    accent-insensitive.
    """
    haystack = _strip_accents(text).lower()
    start_idx = -1
    for lbl in start_labels:
        needle = _strip_accents(lbl).lower()
        m = re.search(rf"\b{re.escape(needle)}\b\s*:?", haystack)
        if m and (start_idx == -1 or m.start() < start_idx):
            start_idx = m.end()
    if start_idx == -1:
        return None

    end_idx = len(text)
    for lbl in stop_labels:
        needle = _strip_accents(lbl).lower()
        m = re.search(rf"\b{re.escape(needle)}\b\s*:?", haystack[start_idx:])
        if m:
            candidate = start_idx + m.start()
            if candidate < end_idx:
                end_idx = candidate
    return text[start_idx:end_idx].strip()


def _parse_french_date(text: str) -> str | None:
    """Parse '16 Janvier 2026' → '2026-01-16' (ISO)."""
    if not text:
        return None
    t = _strip_accents(text).lower()
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m:
        day, month_name, year = m.groups()
        month = FRENCH_MONTHS.get(month_name) or FRENCH_MONTHS.get(month_name.strip("."))
        if month:
            try:
                return datetime(int(year), month, int(day)).date().isoformat()
            except ValueError:
                return None
    # dd/mm/yyyy fallback
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", t)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return datetime(y, mo, d).date().isoformat()
        except ValueError:
            return None
    return None


def _parse_nb_postes(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- #
# Field extractors
# --------------------------------------------------------------------------- #

def extract_reference(text: str) -> str | None:
    patterns = [
        r"R[ée]f[ée]rence\s*_?\s*Annonce\s*:\s*([A-Za-z0-9 _/\-\.]+?)(?:\n|$)",
        r"R[ée]f[ée]rence\s*:\s*([A-Za-z0-9 _/\-\.]+?)(?:\n|$)",
        r"\bR[ée]f\s*[:\-_]\s*([A-Za-z0-9 _/\-\.]+?)(?:\n|$)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return _normalize_ws(m.group(1)).rstrip(".-_")
    return None


def extract_poste(text: str, titre_fallback: str | None) -> str | None:
    patterns = [
        r"pour\s+le\s+poste\s+de\s*:?\s*\n?\s*([^\n]+)",
        r"POSTE\s+DE\s+([A-ZÉÀÈÊÎÔÛÇ][^\n]+)",
        r"Poste\s*:\s*([^\n]+)",
        r"Profil\s+recherch[ée]\s*\n\s*([^\n]+)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            candidate = _normalize_ws(m.group(1))
            # Reject obvious narrative sentences masquerading as job titles.
            starts_sentence = re.match(
                r"^(Rattach|Vous|Nous|Sous|Au\s+sein|Dans\s+le|Le\s+|La\s+)",
                candidate,
                re.IGNORECASE,
            )
            if 3 < len(candidate) < 120 and not starts_sentence:
                return candidate
    if titre_fallback:
        # Clean up common prefixes in source titles
        cleaned = re.sub(
            r"^(Avis\s+de\s+concours\s+de\s+recrutement\s+de|Publication\s+de\s+la\s+liste.*?de)\s*",
            "",
            titre_fallback,
            flags=re.IGNORECASE,
        )
        return _normalize_ws(cleaned.strip("( "))
    return None


def extract_age_max(text: str) -> int | None:
    m = re.search(r"moins\s+de\s+(\d{2})\s*ans", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_nationalite(text: str) -> str | None:
    m = re.search(r"nationalit[ée]\s+([A-Za-zéèê]+)", text, re.IGNORECASE)
    return m.group(1).capitalize() if m else None


def extract_diplome_niveau(text: str) -> str | None:
    """Return the highest Bac+X requirement found, or Doctorat/Master/Ingénieur."""
    levels = re.findall(r"Bac\s*\+\s*(\d)", text, re.IGNORECASE)
    if levels:
        return f"Bac+{max(int(x) for x in levels)}"
    if re.search(r"\bdoctorat\b", text, re.IGNORECASE):
        return "Doctorat"
    if re.search(r"\bingenieur|ingénieur\b", text, re.IGNORECASE):
        return "Ingénieur"
    if re.search(r"\bmaster\b", text, re.IGNORECASE):
        return "Master"
    if re.search(r"\blicence\b", text, re.IGNORECASE):
        return "Licence"
    return None


def extract_experience_min(text: str) -> int | None:
    patterns = [
        r"(?:minimum\s+de\s+|au\s+moins\s+|d'au\s+moins\s+|de\s+minimum\s+)(\d{1,2})\s*(?:an|années|ans)",
        r"exp[ée]rience\s+(?:professionnelle\s+)?(?:de\s+)?(\d{1,2})\s*(?:an|ans|années)",
        r"(\d{1,2})\s*(?:ans|années)\s+d'?\s*exp[ée]rience",
    ]
    values: list[int] = []
    for p in patterns:
        values += [int(m) for m in re.findall(p, text, re.IGNORECASE)]
    return min(values) if values else None


def extract_lieu(text: str) -> str | None:
    m = re.search(r"Affectation\s*:\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        return _normalize_ws(m.group(1))
    m = re.search(r"Poste[s]?\s+bas[ée]\(?s?\)?\s+(?:à|a)\s+([A-Za-zéèêàâ\- ]+)", text, re.IGNORECASE)
    if m:
        return _normalize_ws(m.group(1))
    m = re.search(r"\(\s*Poste[s]?\s+bas[ée]\(?s?\)?\s+(?:à|a)\s+([A-Za-zéèêàâ\- ]+?)\s*\)", text, re.IGNORECASE)
    if m:
        return _normalize_ws(m.group(1))
    return None


# Canonical form for accented/unaccented variants
_CITY_CANONICAL = {
    "sale": "Salé", "salé": "Salé",
    "fes": "Fès", "fès": "Fès",
    "meknes": "Meknès", "meknès": "Meknès",
    "tetouan": "Tétouan", "tétouan": "Tétouan",
    "kenitra": "Kénitra", "kénitra": "Kénitra",
    "laayoune": "Laâyoune", "laâyoune": "Laâyoune",
}


def extract_villes(text: str) -> list[str]:
    found: set[str] = set()
    for city in MOROCCAN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", text, re.IGNORECASE):
            canonical = _CITY_CANONICAL.get(city.lower(), city)
            found.add(canonical)
    return sorted(found)


def derive_villes(*sources: str | None) -> list[str]:
    """
    Merge ville detections from several text sources (description, lieu,
    ville_principale, title). Guarantees a non-empty list if any of the
    sources names a city — this is the main reason emploi-public and
    adzuna records were shipping with `villes: []`.

    Note : on délègue le filtrage pays/région/département aux consommateurs
    via `geo_normalizer.normalize_villes`, qui est appelé dans chaque
    transformer + dans l'ETL avant insertion dans `dim_ville`.
    """
    found: set[str] = set()
    for s in sources:
        if not s:
            continue
        found.update(extract_villes(s))
    return sorted(found)


# Short/ambiguous tech tokens need stricter matching to avoid picking up
# random capitalized words (e.g. "Go" in "GO-ASNIÈRES", "R" in "R&D" prose).
_STRICT_TECH = {"R", "Go", "C", "C#", "C++"}


def extract_technologies(text: str) -> list[str]:
    found = set()
    for tech in TECH_KEYWORDS:
        if tech in _STRICT_TECH:
            # Require surrounding punctuation typical of a tech list
            # (comma, slash, parens, "et"/"and"/"ou"/"/") or explicit context
            # like "langage R" / "Go language".
            pattern = (
                rf"(?:langage|language|en|using|avec|with|stack|maitrise|"
                rf"ma[iî]trise|connaissance|programmation|dev(?:eloppement)?|code|coding)\s+"
                rf"(?:[a-z]+\s+)?{re.escape(tech)}(?![A-Za-z0-9+#])"
                rf"|[\(\[,;/]\s*{re.escape(tech)}\s*[\)\],;/]"
                rf"|\b{re.escape(tech)}\b(?=\s*[,;/\)\]]|\s+(?:et|and|ou|or)\s+)"
            )
            if re.search(pattern, text, re.IGNORECASE):
                found.add(tech)
        else:
            pattern = rf"(?<![A-Za-z0-9]){re.escape(tech)}(?![A-Za-z0-9])"
            if re.search(pattern, text, re.IGNORECASE):
                found.add(tech)
    return sorted(found)


def extract_langues(text: str) -> list[str]:
    lowered = _strip_accents(text).lower()
    found = []
    for lang in LANGUAGES:
        key = _strip_accents(lang).lower()
        if re.search(rf"\b{key}\b", lowered):
            label = lang.capitalize()
            if label not in found:
                found.append(label)
    return found


def extract_emails(text: str) -> list[str]:
    return sorted(set(EMAIL_RE.findall(text)))


def extract_urls(text: str) -> list[str]:
    urls = URL_RE.findall(text)
    cleaned = [u.rstrip(".,;:)") for u in urls]
    return sorted(set(cleaned))


def extract_missions(text: str) -> list[str]:
    section = _section(
        text,
        start_labels=[
            "Activités principales", "Activites principales", "Activités",
            "Missions principales", "Principales missions", "Missions",
            "Responsabilités et Activités principales", "Responsabilités",
            "Tâches", "Taches",
        ],
        stop_labels=[
            "Compétences", "Competences", "Profil requis", "Profil recherche",
            "Profil recherché", "Qualifications", "Conditions", "Dossier de candidature",
        ],
    )
    return _split_bullets(section) if section else []


def extract_competences(text: str) -> list[str]:
    section = _section(
        text,
        start_labels=[
            "Compétences requises pour le poste", "Compétences requises",
            "Compétences et Qualités", "Compétences", "Competences",
            "Qualifications",
        ],
        stop_labels=[
            "Profil requis", "Profil recherche", "Profil recherché",
            "Dossier de candidature", "Modalités", "Conditions",
            "Date et lieu", "Date limite",
        ],
    )
    return _split_bullets(section) if section else []


def extract_profil(text: str) -> list[str]:
    section = _section(
        text,
        start_labels=[
            "Profil requis", "Profil recherché", "Profil recherche",
            "Profil", "Conditions d'éligibilité", "Conditions d'eligibilite",
        ],
        stop_labels=[
            "Dossier de candidature", "Modalités", "Modalites",
            "Date et lieu", "Date limite", "Affectation",
            "Compétences", "Competences",
        ],
    )
    return _split_bullets(section) if section else []


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def transform_offer(raw: dict[str, Any]) -> dict[str, Any]:
    description = raw.get("description") or ""
    title = raw.get("titre")

    poste = extract_poste(description, title)
    lieu = extract_lieu(description)
    villes = derive_villes(description, lieu, title)
    experience = extract_experience_min(description)
    diplome = extract_diplome_niveau(description)

    salary = parse_salary_from_text(description) or estimate_salary_mad(
        poste=poste, titre=title,
        experience_years=experience, diplome_niveau=diplome,
    )

    record: dict[str, Any] = {
        "source": raw.get("source"),
        "source_id": (raw.get("_id") or {}).get("$oid"),
        "url": raw.get("url"),
        "titre_original": title,
        "poste": poste,
        "societe": raw.get("societe"),
        "type_annonce": raw.get("type_annonce"),
        "statut": raw.get("statut"),
        "reference": extract_reference(description),
        "nb_postes": _parse_nb_postes(raw.get("nb_postes")),
        "date_limite_raw": raw.get("date_limite"),
        "date_limite": _parse_french_date(raw.get("date_limite") or ""),
        "scraped_at": (raw.get("scraped_at") or {}).get("$date"),
        "lieu": lieu,
        "villes": villes,
        "age_max": extract_age_max(description),
        "nationalite": extract_nationalite(description),
        "diplome_niveau": diplome,
        "experience_min_annees": experience,
        "salaire_min": salary["salaire_min"],
        "salaire_max": salary["salaire_max"],
        "devise": salary["devise"],
        "source_salaire": salary["source_salaire"],
        "langues": extract_langues(description),
        "technologies": normalize_skills(extract_technologies(description)),
        "missions": extract_missions(description),
        "competences": extract_competences(description),
        "profil": extract_profil(description),
        "emails_contact": extract_emails(description),
        "urls_postulation": extract_urls(description),
        "description_brute": description,
    }
    return enrich(record, source_id=1)


def load_offers(path: Path) -> list[dict[str, Any]]:
    """Load the raw file which is JSON-lines (one document per line)."""
    offers: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                offers.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed line %d: %s", i, exc)
    return offers


def run() -> None:
    logger.info("Reading raw offers from %s", INPUT_FILE)
    offers = load_offers(INPUT_FILE)
    logger.info("Loaded %d raw offers", len(offers))

    annonces = [o for o in offers if (o.get("type_annonce") or "").strip().lower() == "annonce"]
    logger.info("Kept %d offers with type_annonce == 'Annonce'", len(annonces))

    transformed: list[dict[str, Any]] = []
    for o in annonces:
        try:
            rec = transform_offer(o)
            if not (rec.get("description_brute") or "").strip():
                logger.info("Skipping offer without description: %s", rec.get("url"))
                continue
            transformed.append(rec)
            logger.info(
                "Transformed offer | poste=%r | societe=%r | date_limite=%s | tech=%d | missions=%d | competences=%d",
                rec.get("poste"), rec.get("societe"), rec.get("date_limite"),
                len(rec.get("technologies") or []),
                len(rec.get("missions") or []),
                len(rec.get("competences") or []),
            )
        except Exception:
            logger.exception("Failed to transform offer %s", o.get("url"))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(transformed, fh, ensure_ascii=False, indent=2)

    logger.info("Wrote %d cleaned offers to %s", len(transformed), OUTPUT_FILE)


if __name__ == "__main__":
    run()
