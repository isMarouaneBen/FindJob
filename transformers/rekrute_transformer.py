"""
Transformer for rekrute.com scraped job offers.

Rekrute offers have a very different shape from emploi-public: there is
already a structured `infos` dict (experience, region, education, contract,
remote) and the free-text `description` is built from sections separated by
` | ` (Entreprise, Poste, Profil recherché, Adresse, Traits de personnalité,
Culture de l'entreprise, ...).

This transformer normalizes everything into the same target schema as the
emploi-public transformer so downstream consumers can treat all sources
uniformly. Heuristics & keyword extractors are imported from the
emploi_public transformer to stay DRY.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from emploi_public_transformer import (  # type: ignore
    _clean_line,
    _normalize_ws,
    _split_bullets,
    derive_villes,
    extract_age_max,
    extract_emails,
    extract_langues,
    extract_technologies,
    extract_urls,
    extract_villes,
)
from salary_estimator import estimate_salary_mad, parse_salary_from_text

# --------------------------------------------------------------------------- #
# Paths & logging
# --------------------------------------------------------------------------- #

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
INPUT_FILE = BASE_DIR / "data" / "rekrute_raw.json"
OUTPUT_FILE = BASE_DIR / "data" / "rekrute_clean.json"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "rekrute_transformer.log"

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
logger = logging.getLogger("rekrute_transformer")


# --------------------------------------------------------------------------- #
# Section labels (rekrute description is split by ` | `)
# --------------------------------------------------------------------------- #

SECTION_LABELS = {
    "entreprise":   ["Entreprise"],
    "culture":      ["Culture de l'entreprise", "Culture de l’entreprise"],
    "poste":        ["Poste", "Mission", "Missions"],
    "profil":       ["Profil recherché", "Profil recherche", "Profil"],
    "adresse":      ["Adresse de notre siège", "Adresse"],
    "traits":       ["Traits de personnalité souhaités", "Traits de personnalité"],
}

# Footer block we don't want in any section (rekrute UI noise).
FOOTER_MARKERS = [
    "4K Matching", "FineTunePro", "Kapacity Revealer", "Feel Good CULTURE",
    "Connectez-vous", "Inscrivez-vous",
]

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _strip_footer(text: str) -> str:
    """Cut the rekrute UI footer (matching widgets, login prompts, ...)."""
    cut = len(text)
    for marker in FOOTER_MARKERS:
        idx = text.find(marker)
        if idx != -1 and idx < cut:
            cut = idx
    return text[:cut].strip(" |\t\r\n")


def split_sections(description: str) -> dict[str, str]:
    """
    Split a rekrute description on ` | ` and assign each chunk to a known
    section based on its leading label. Unrecognized chunks are appended to
    a `_other` bucket.
    """
    if not description:
        return {}

    cleaned = _strip_footer(description)
    chunks = [c.strip() for c in cleaned.split("|") if c.strip()]
    out: dict[str, str] = {}

    for chunk in chunks:
        matched = False
        for key, labels in SECTION_LABELS.items():
            for lbl in labels:
                m = re.match(rf"\s*{re.escape(lbl)}\s*:\s*(.*)$", chunk, re.IGNORECASE | re.DOTALL)
                if m:
                    body = _normalize_ws(m.group(1))
                    if body:
                        out[key] = (out.get(key, "") + " " + body).strip()
                    matched = True
                    break
            if matched:
                break
        if not matched:
            out["_other"] = (out.get("_other", "") + " | " + chunk).strip(" |")
    return out


def _split_rekrute_bullets(block: str) -> list[str]:
    """
    Rekrute often uses dotted markers `•` or simple periods/numbers. Reuse
    the generic bullet splitter then fall back to sentence segmentation.
    """
    items = _split_bullets(block)
    if len(items) > 1:
        return items
    # Fall back to a sentence split for blocks written as flowing prose.
    sentences = re.split(r"(?<=[.;])\s+(?=[A-ZÉÈÀÂÎÔÛ])", block)
    return [_clean_line(s) for s in sentences if _clean_line(s) and len(s) > 5]


# --------------------------------------------------------------------------- #
# Field extractors specific to rekrute
# --------------------------------------------------------------------------- #

def parse_date(value: str | None) -> str | None:
    """Convert dd/mm/yyyy → ISO 8601."""
    if not value:
        return None
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    try:
        return datetime(y, mo, d).date().isoformat()
    except ValueError:
        return None


def clean_titre(titre: str | None) -> str | None:
    """`Responsable Satisfaction Client (H/F) | Rabat (Maroc)` → poste only."""
    if not titre:
        return None
    return _normalize_ws(titre.split("|")[0])


def parse_region(value: str | None) -> dict[str, Any]:
    """Parse `1poste(s) sur Rabat et région - Maroc` into nb_postes + lieu."""
    if not value:
        return {"nb_postes": None, "lieu": None, "pays": None}
    nb_match = re.search(r"(\d+)\s*poste", value, re.IGNORECASE)
    nb = int(nb_match.group(1)) if nb_match else None

    # Strip the "Xposte(s) sur" prefix
    rest = re.sub(r"^\s*\d+\s*poste\(?s?\)?\s*sur\s*", "", value, flags=re.IGNORECASE)
    rest = _normalize_ws(rest)
    pays = None
    if " - " in rest:
        lieu_part, pays = [p.strip() for p in rest.rsplit(" - ", 1)]
    else:
        lieu_part = rest
    return {"nb_postes": nb, "lieu": lieu_part or None, "pays": pays}


def parse_experience(value: str | None) -> dict[str, Any]:
    """`Intermédiaire (3 à 5 ans)` → label + min/max years."""
    if not value:
        return {"experience_label": None, "experience_min_annees": None, "experience_max_annees": None}
    label_match = re.match(r"\s*([^()]+?)\s*\(", value)
    label = _normalize_ws(label_match.group(1)) if label_match else _normalize_ws(value)
    rng = re.search(r"(\d+)\s*(?:à|a|-)\s*(\d+)\s*ans?", value, re.IGNORECASE)
    if rng:
        return {
            "experience_label": label,
            "experience_min_annees": int(rng.group(1)),
            "experience_max_annees": int(rng.group(2)),
        }
    single = re.search(r"(\d+)\s*ans?", value)
    if single:
        n = int(single.group(1))
        return {"experience_label": label, "experience_min_annees": n, "experience_max_annees": n}
    return {"experience_label": label, "experience_min_annees": None, "experience_max_annees": None}


def parse_niveau_etude(value: str | None) -> dict[str, Any]:
    """`Bac +5 et plus Minimum - Ecole d'ingénieur - Master` → niveau + types."""
    if not value:
        return {"diplome_niveau": None, "diplome_types": []}
    cleaned = _normalize_ws(value)
    parts = [p.strip() for p in re.split(r"\s*-\s*", cleaned) if p.strip()]
    niveau = parts[0] if parts else None
    types = [p for p in parts[1:] if p.lower() != "minimum"]
    return {"diplome_niveau": niveau, "diplome_types": types}


def parse_teletravail(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"T[ée]l[ée]travail\s*:\s*(.+)", value, re.IGNORECASE)
    return _normalize_ws(m.group(1)) if m else _normalize_ws(value)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def transform_offer(raw: dict[str, Any]) -> dict[str, Any]:
    description = raw.get("description") or ""
    sections = split_sections(description)

    poste_text = sections.get("poste", "")
    profil_text = sections.get("profil", "")
    entreprise_text = sections.get("entreprise", "")
    full_text_for_kw = f"{poste_text} {profil_text} {entreprise_text}"

    infos = raw.get("infos") or {}
    region = parse_region(infos.get("région") or infos.get("region"))
    experience = parse_experience(infos.get("expérience_requise") or infos.get("experience_requise"))
    etude = parse_niveau_etude(infos.get("niveau_détude_et_formation") or infos.get("niveau_detude_et_formation"))

    poste = clean_titre(raw.get("titre"))
    villes = derive_villes(description, region["lieu"], raw.get("titre"), sections.get("adresse"))
    salaire_infos = infos.get("salaire") or infos.get("rémunération") or infos.get("remuneration")
    salary = (
        parse_salary_from_text(salaire_infos)
        or parse_salary_from_text(description)
        or estimate_salary_mad(
            poste=poste,
            titre=raw.get("titre"),
            experience_years=experience["experience_min_annees"],
            diplome_niveau=etude["diplome_niveau"],
        )
    )

    record: dict[str, Any] = {
        "source": raw.get("source"),
        "source_id": (raw.get("_id") or {}).get("$oid"),
        "url": raw.get("url"),
        "titre_original": raw.get("titre"),
        "poste": poste,
        "societe": _extract_societe(entreprise_text, raw.get("url")),
        "type_annonce": "Annonce",  # rekrute records are all job ads
        "statut": raw.get("statut"),
        "reference": None,  # rekrute does not expose a reference number
        "nb_postes": region["nb_postes"],
        "date_debut": parse_date(raw.get("date_debut")),
        "date_limite_raw": raw.get("date_limite"),
        "date_limite": parse_date(raw.get("date_limite")),
        "scraped_at": (raw.get("scraped_at") or {}).get("$date"),
        "lieu": region["lieu"] or sections.get("adresse"),
        "pays": region["pays"],
        "villes": villes,
        "salaire_min": salary["salaire_min"],
        "salaire_max": salary["salaire_max"],
        "devise": salary["devise"],
        "source_salaire": salary["source_salaire"],
        "type_contrat": infos.get("type_de_contrat"),
        "teletravail": parse_teletravail(infos.get("télétravail") or infos.get("teletravail")),
        "experience_label": experience["experience_label"],
        "experience_min_annees": experience["experience_min_annees"],
        "experience_max_annees": experience["experience_max_annees"],
        "diplome_niveau": etude["diplome_niveau"],
        "diplome_types": etude["diplome_types"],
        "age_max": extract_age_max(description),
        "langues": extract_langues(description),
        "technologies": extract_technologies(full_text_for_kw),
        "missions": _split_rekrute_bullets(poste_text),
        "competences": _split_rekrute_bullets(profil_text),
        "profil": _split_rekrute_bullets(profil_text),
        "traits_personnalite": [t for t in _split_rekrute_bullets(sections.get("traits", "")) if t],
        "culture_entreprise": sections.get("culture"),
        "presentation_entreprise": entreprise_text or None,
        "adresse": sections.get("adresse"),
        "emails_contact": extract_emails(description),
        "urls_postulation": extract_urls(description),
        "description_brute": description,
    }
    return record


def _extract_societe(entreprise_text: str, url: str | None) -> str | None:
    """
    Rekrute embeds the company name in the URL slug
    (`...-recrutement-<slug>-<city>-<id>.html`). Use that as a robust source.
    Fall back to the first sentence of the Entreprise section.
    """
    if url:
        m = re.search(r"-recrutement-([a-z0-9\-]+?)-(?:[a-z\-]+)?-?\d+\.html", url, re.IGNORECASE)
        if m:
            slug = m.group(1).replace("-", " ").strip()
            if slug:
                return slug.title()
    if entreprise_text:
        first = re.split(r"(?<=[.!?])\s+", entreprise_text, maxsplit=1)[0]
        return _normalize_ws(first)[:200] or None
    return None


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

    # Rekrute records have no `type_annonce` field — they are all job ads.
    # We still apply a defensive filter on `statut` in case inactive entries
    # appear in the future, and require a non-empty description.
    kept = [o for o in offers if (o.get("description") or "").strip()]
    if (skipped := len(offers) - len(kept)):
        logger.info("Skipped %d offers without description", skipped)

    transformed: list[dict[str, Any]] = []
    for o in kept:
        try:
            rec = transform_offer(o)
            transformed.append(rec)
            logger.info(
                "Transformed offer | poste=%r | societe=%r | lieu=%r | contrat=%s | exp=%s | tech=%d | missions=%d | competences=%d",
                rec.get("poste"), rec.get("societe"), rec.get("lieu"),
                rec.get("type_contrat"), rec.get("experience_label"),
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
