"""
Transformer for Adzuna scraped job offers.

Adzuna records come from a well-typed API, so most metadata is already
structured (company, location hierarchy, salary range, contract time,
creation date, ...). The `description` field, however, is usually a
short teaser (often truncated with `…`) that mixes English and French
prose with no predictable section headers.

This transformer normalizes every record into the same target schema as
the emploi-public and rekrute transformers so downstream consumers can
treat all sources uniformly. Heuristics & keyword extractors are
imported from the emploi_public transformer to stay DRY.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from emploi_public_transformer import (  # type: ignore
    _normalize_ws,
    derive_villes,
    extract_emails,
    extract_langues,
    extract_technologies,
    extract_urls,
    extract_villes,
)
from enrichment import enrich  # type: ignore
from geo_normalizer import (  # type: ignore
    is_non_ville,
    normalize_ville,
    normalize_villes,
    pick_city_from_area,
)
from salary_estimator import (
    EUR_TO_MAD,
    estimate_salary_eur,
    estimate_salary_mad,
    parse_salary_from_text,
)
from skill_normalizer import normalize_skills  # type: ignore

# --------------------------------------------------------------------------- #
# Paths & logging
# --------------------------------------------------------------------------- #

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
INPUT_FILE = BASE_DIR / "data" / "adzuna_raw.json"
OUTPUT_FILE = BASE_DIR / "data" / "adzuna_clean.json"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "adzuna_transformer.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
    force=True,
)
logger = logging.getLogger("adzuna_transformer")


# --------------------------------------------------------------------------- #
# Lightweight inference helpers (Adzuna has no explicit section structure)
# --------------------------------------------------------------------------- #

# Contract time codes used by Adzuna.
CONTRACT_TIME_MAP = {
    "full_time": "Temps plein",
    "part_time": "Temps partiel",
}
CONTRACT_TYPE_MAP = {
    "permanent": "CDI",
    "contract": "CDD",
}

# Ordered: first match wins.
SENIORITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Stage",        re.compile(r"\b(stage|internship|stagiaire|intern)\b", re.IGNORECASE)),
    ("Alternance",   re.compile(r"\b(alternance|apprenti(?:e|ssage)?)\b", re.IGNORECASE)),
    ("Junior",       re.compile(r"\bjunior\b", re.IGNORECASE)),
    ("Senior",       re.compile(r"\b(senior|expert|principal|lead)\b", re.IGNORECASE)),
    ("Confirmé",     re.compile(r"\bconfirm[ée]\b", re.IGNORECASE)),
]

# Contract type hints discovered in title or description when the API
# field is null (which is the common case on the FR endpoint).
CONTRACT_HINT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Stage",      re.compile(r"\b(stage|internship|stagiaire|intern)\b", re.IGNORECASE)),
    ("Alternance", re.compile(r"\b(alternance|apprenti(?:e|ssage)?)\b", re.IGNORECASE)),
    ("CDI",        re.compile(r"\bCDI\b")),
    ("CDD",        re.compile(r"\bCDD\b")),
    ("Freelance",  re.compile(r"\bfreelance\b", re.IGNORECASE)),
]


def infer_seniority(*blobs: str | None) -> str | None:
    text = " ".join(b for b in blobs if b)
    for label, pat in SENIORITY_PATTERNS:
        if pat.search(text):
            return label
    return None


def infer_contract_type(api_value: str | None, *blobs: str | None) -> str | None:
    if api_value:
        return CONTRACT_TYPE_MAP.get(api_value, api_value)
    text = " ".join(b for b in blobs if b)
    for label, pat in CONTRACT_HINT_PATTERNS:
        if pat.search(text):
            return label
    return None


def infer_teletravail(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    if re.search(r"\b(100%\s*remote|full\s*remote|t[ée]l[ée]travail\s+total)\b", lowered):
        return "Total"
    if re.search(r"\b(hybride|hybrid)\b", lowered):
        return "Hybride"
    if re.search(r"\bremote\b|t[ée]l[ée]travail", lowered):
        return "Possible"
    return None


def parse_iso_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        # Adzuna uses `2026-04-06T22:25:01Z`
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").isoformat() + "Z"
    except ValueError:
        return value


def parse_salary(min_val: Any, max_val: Any, devise: Any) -> dict[str, Any]:
    """
    Adzuna FR mélange parfois TJM freelance (€/jour) et salaire annuel
    dans les mêmes champs. Heuristique : valeur < 1500 EUR ≈ TJM →
    on convertit en annuel via 218 jours ouvrés ETP.
    """
    def _num(v: Any) -> float | None:
        try:
            n = float(v)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    lo = _num(min_val)
    hi = _num(max_val)
    dev = devise if devise not in (None, "", "0", 0) else None

    # TJM detection : si EUR et borne haute < 1500, on considère que c'est un TJM.
    if dev == "EUR" or dev is None:
        if lo is not None and (hi is None or hi < 1500) and lo < 1500:
            WORKING_DAYS = 218
            lo = lo * WORKING_DAYS
            if hi is not None:
                hi = hi * WORKING_DAYS
            dev = "EUR"

    # Garde-fou : couple incohérent (ex: min=45, max=45000) — la borne basse
    # est manifestement corrompue côté source. On la remonte à 70% du max.
    if lo is not None and hi is not None and hi > 0 and lo < hi * 0.10 and lo < 1000:
        lo = round(hi * 0.7)

    return {"salaire_min": lo, "salaire_max": hi, "devise": dev}


def parse_location(raw: dict[str, Any]) -> dict[str, Any]:
    """
    `location_area` est ordonné [pays, région, dpt, ..., ville].
    On prend `pays` = area[0] mais on ne considère comme ville que le dernier
    élément qui n'est ni un pays, ni une région, ni un département. Si tout
    est blacklisté (annonce nationale type ["France"]) on renvoie ville=None
    pour que l'ETL retombe sur le sentinel "Non spécifié".
    """
    area = raw.get("location_area") or []
    pays = area[0] if len(area) >= 1 else None
    # Région = première entrée après le pays qui ressemble à une région FR.
    region = area[1] if len(area) >= 2 else None
    ville = pick_city_from_area(area)
    # En dernier recours : `localisation` (ex. "Paris, Ile-de-France") — on
    # garde la première portion avant la virgule si c'est une vraie ville.
    if not ville:
        loc = raw.get("localisation") or ""
        head = loc.split(",", 1)[0].strip() if loc else ""
        ville = normalize_ville(head)
    return {
        "pays": pays,
        "region": region,
        "ville_principale": ville,
        "localisation": raw.get("localisation"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
    }


def clean_description(text: str | None) -> str | None:
    """Collapse whitespace and strip the trailing `…` truncation marker."""
    if not text:
        return None
    cleaned = _normalize_ws(text)
    return cleaned.rstrip("… .").strip() or None


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def transform_offer(raw: dict[str, Any]) -> dict[str, Any]:
    description = clean_description(raw.get("description")) or ""
    titre = raw.get("titre")

    location = parse_location(raw)
    salary = parse_salary(raw.get("salaire_min"), raw.get("salaire_max"), raw.get("devise"))

    # Adzuna = source FR : si pas de figures source, on parse le texte puis
    # on retombe sur une estimation EUR (et NON MAD comme avant — c'était
    # incohérent puisque tout Adzuna est en France).
    source_salaire = "source" if salary["salaire_min"] else None
    if salary["salaire_min"] is None:
        parsed = parse_salary_from_text(description)
        if parsed:
            salary = {"salaire_min": parsed["salaire_min"], "salaire_max": parsed["salaire_max"], "devise": parsed["devise"]}
            source_salaire = parsed["source_salaire"]
        else:
            est = estimate_salary_eur(poste=titre, titre=titre)
            salary = {"salaire_min": est["salaire_min"], "salaire_max": est["salaire_max"], "devise": est["devise"]}
            source_salaire = est["source_salaire"]

    # Si la source a renvoyé un montant mais sans devise (cas devise="0"),
    # on force EUR puisqu'on est sur l'endpoint Adzuna FR.
    if salary["salaire_min"] and not salary.get("devise"):
        salary["devise"] = "EUR"

    # Provide MAD-normalized figures to unify cross-source comparison.
    if salary["devise"] == "MAD":
        salaire_min_mad, salaire_max_mad = salary["salaire_min"], salary["salaire_max"]
    elif salary["devise"] == "EUR" and salary["salaire_min"] is not None:
        # Adzuna EUR figures are annual; normalize to monthly gross.
        salaire_min_mad = round(float(salary["salaire_min"]) * EUR_TO_MAD / 12)
        salaire_max_mad = round(float(salary["salaire_max"]) * EUR_TO_MAD / 12)
    else:
        salaire_min_mad = salaire_max_mad = None

    contract_time = raw.get("contract_time")
    contract_type = infer_contract_type(raw.get("contract_type"), titre, description)
    seniority = infer_seniority(titre, description)

    # Adzuna descriptions are teasers, so keyword search on title+description
    # remains the most reliable signal we have for tech stack.
    keyword_text = f"{titre or ''} {description}"

    record: dict[str, Any] = {
        "source": raw.get("source"),
        "source_id": (raw.get("_id") or {}).get("$oid"),
        "adzuna_id": raw.get("adzuna_id"),
        "url": raw.get("url"),
        "titre_original": titre,
        "poste": titre,
        "societe": raw.get("entreprise"),
        "type_annonce": "Annonce",  # Adzuna results are all job ads
        "statut": raw.get("statut"),
        "categorie": raw.get("categorie") if raw.get("categorie") != "Unknown" else None,
        "reference": raw.get("adzuna_id"),
        "nb_postes": 1,  # Adzuna always lists a single opening per ad
        "date_publication": parse_iso_datetime(raw.get("created")),
        "date_limite": None,  # Adzuna does not expose a closing date
        "scraped_at": (raw.get("scraped_at") or {}).get("$date"),
        "lieu": location["localisation"],
        "pays": location["pays"],
        "region": location["region"],
        "ville_principale": location["ville_principale"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "villes": normalize_villes(
            derive_villes(
                description, titre, location.get("localisation"),
                location.get("ville_principale"), location.get("region"),
            ) or ([location["ville_principale"]] if location.get("ville_principale") else [])
        ),
        "type_contrat": contract_type,
        "temps_travail": CONTRACT_TIME_MAP.get(contract_time or "", contract_time),
        "teletravail": infer_teletravail(description),
        "seniorite": seniority,
        "salaire_min": salary["salaire_min"],
        "salaire_max": salary["salaire_max"],
        "devise": salary["devise"],
        "salaire_min_mad": salaire_min_mad,
        "salaire_max_mad": salaire_max_mad,
        "source_salaire": source_salaire,
        "langues": extract_langues(description),
        "technologies": normalize_skills(extract_technologies(keyword_text)),
        "emails_contact": extract_emails(description),
        "urls_postulation": extract_urls(description),
        "description_brute": description or None,
    }
    return enrich(record, source_id=3)


def load_offers(path: Path) -> list[dict[str, Any]]:
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

    # Adzuna records have no `type_annonce` field — they are all job ads by
    # construction. We still filter out entries without a description or a
    # title, since those are unusable downstream.
    kept = [
        o for o in offers
        if (o.get("titre") or "").strip() and (o.get("description") or "").strip()
    ]
    skipped = len(offers) - len(kept)
    if skipped:
        logger.info("Skipped %d offers missing title or description", skipped)

    transformed: list[dict[str, Any]] = []
    dedup_ids: set[str] = set()
    for o in kept:
        try:
            rec = transform_offer(o)
            aid = rec.get("adzuna_id")
            if aid and aid in dedup_ids:
                logger.info("Skipping duplicate adzuna_id=%s", aid)
                continue
            if aid:
                dedup_ids.add(aid)
            transformed.append(rec)
            logger.info(
                "Transformed offer | poste=%r | societe=%r | lieu=%r | contrat=%s | seniorite=%s | tech=%d",
                rec.get("poste"), rec.get("societe"), rec.get("lieu"),
                rec.get("type_contrat"), rec.get("seniorite"),
                len(rec.get("technologies") or []),
            )
        except Exception:
            logger.exception("Failed to transform offer %s", o.get("url"))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(transformed, fh, ensure_ascii=False, indent=2)

    logger.info("Wrote %d cleaned offers to %s", len(transformed), OUTPUT_FILE)


if __name__ == "__main__":
    run()
