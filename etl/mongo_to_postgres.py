"""
ETL Mongo (bronze, raw) -> Postgres (gold, star schema `analytics`).

Pipeline par source :
    1. Lecture d'un batch de documents bruts dans `job_raw.{source}_raw`
    2. Passage dans le transformer Python existant (scrapers/transformers/)
       -> on obtient le même dict que dans data/{source}_clean.json
    3. UPSERT dans `analytics.fact_offer` + hydratation des dimensions
       et des tables pont.

Stratégie anti-NULL :
    - chaque dim possède une ligne sentinel id=0 "Non spécifié".
    - lookup/insert atomique via INSERT ... ON CONFLICT DO NOTHING puis SELECT.
    - toute valeur manquante -> FK=0 (NOT NULL respecté).
    - dates inconnues -> date_id=19000101 (publication/scraping) ou 99991231 (limite).

Usage :
    python etl/mongo_to_postgres.py                       # toutes les sources
    python etl/mongo_to_postgres.py --source rekrute      # une seule source
    python etl/mongo_to_postgres.py --limit 100           # debug
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime, date
from pathlib import Path
from typing import Any, Callable, Iterable

import psycopg2
import psycopg2.extras
from pymongo import MongoClient

# --------------------------------------------------------------------------- #
# Import des transformers existants
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "transformers"))

import emploi_public_transformer as t_emploi
import rekrute_transformer as t_rekrute
import adzuna_transformer as t_adzuna

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:admin123@localhost:27017/")
MONGO_DB  = os.getenv("MONGO_DB",  "job_raw")

PG_DSN = os.getenv(
    "POSTGRES_DATA_URI",
    "postgresql://datauser:datapass@localhost:5433/job_db",
)

SOURCES: dict[str, dict[str, Any]] = {
    "emploi_public": {
        "collection": "emploi_public_raw",
        "source_id":  1,
        "transform":  t_emploi.transform_offer,
        "prefilter":  lambda d: (d.get("type_annonce") or "").strip().lower() == "annonce"
                                and bool((d.get("description") or "").strip()),
    },
    "rekrute": {
        "collection": "rekrute_raw",
        "source_id":  2,
        "transform":  t_rekrute.transform_offer,
        "prefilter":  lambda d: bool((d.get("description") or "").strip()),
    },
    "adzuna": {
        "collection": "adzuna_raw",
        "source_id":  3,
        "transform":  t_adzuna.transform_offer,
        "prefilter":  lambda d: bool((d.get("titre") or "").strip())
                                and bool((d.get("description") or "").strip()),
    },
}

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "mongo_to_postgres.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
    force=True,
)
log = logging.getLogger("etl")


# --------------------------------------------------------------------------- #
# Helpers de normalisation pour la correspondance dim
# --------------------------------------------------------------------------- #

_SENTINEL_UNKNOWN_DATE_PUB   = 19000101
_SENTINEL_UNKNOWN_DATE_LIMIT = 99991231


def _slugify(value: str) -> str:
    v = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    v = re.sub(r"[^a-zA-Z0-9]+", "-", v).strip("-").lower()
    return v or "non-specifie"


def _date_to_id(value: Any, *, default: int) -> int:
    """Accepte 'YYYY-MM-DD', ISO datetime, date, None -> date_id (YYYYMMDD)."""
    if not value:
        return default
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            # 'YYYY-MM-DD' ou ISO complet
            d = datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                d = datetime.strptime(s[:10], "%Y-%m-%d").date()
            except ValueError:
                return default
    else:
        return default
    # Les dates hors du range dim_date (2020-2030) basculent au sentinel.
    if d.year < 2020 or d.year > 2030:
        return default
    return int(d.strftime("%Y%m%d"))


# Mapping (code dim) -> {label normalisé: code cible}
_CONTRAT_MAP = {
    "CDI": "CDI", "CDD": "CDD", "STAGE": "Stage",
    "ALTERNANCE": "Alternance", "APPRENTISSAGE": "Alternance",
    "FREELANCE": "Freelance", "INTERIM": "Interim",
}
_TELETRAVAIL_MAP = {
    "NON": "Non", "OUI": "Total",
    "HYBRIDE": "Hybride", "HYBRID": "Hybride",
    "TOTAL": "Total", "POSSIBLE": "Possible", "OCCASIONNEL": "Possible",
    "100%": "Total",
}
_SENIORITE_MAP = {
    "STAGE": "Stage", "ALTERNANCE": "Alternance",
    "JUNIOR": "Junior", "INTERMEDIAIRE": "Intermediaire",
    "CONFIRME": "Confirme", "SENIOR": "Senior",
    "EXPERT": "Expert", "LEAD": "Expert",
}


def _norm(value: str | None) -> str:
    if not value:
        return ""
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().upper().strip()


def _map_contrat(value: str | None) -> str:
    key = _norm(value)
    for k, v in _CONTRAT_MAP.items():
        if k in key:
            return v
    return ""


def _map_teletravail(value: str | None) -> str:
    key = _norm(value)
    for k, v in _TELETRAVAIL_MAP.items():
        if k in key:
            return v
    return ""


def _map_seniorite(value: str | None) -> str:
    key = _norm(value)
    for k, v in _SENIORITE_MAP.items():
        if k in key:
            return v
    return ""


def _map_niveau_diplome(value: str | None) -> str:
    """'Bac +5 et plus Minimum', 'Ingénieur', 'Master' -> code dim_niveau_diplome."""
    if not value:
        return ""
    key = _norm(value)
    m = re.search(r"BAC\s*\+\s*(\d)", key)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 5:
            return f"Bac+{n}"
    if "DOCTORAT" in key or "PHD" in key:
        return "Doctorat"
    if "MASTER" in key or "INGENIEUR" in key or "BAC+5" in key:
        return "Bac+5"
    if "LICENCE" in key or "BAC+3" in key:
        return "Bac+3"
    if "BTS" in key or "DUT" in key or "BAC+2" in key:
        return "Bac+2"
    if "BAC" in key:
        return "Bac"
    return ""


# --------------------------------------------------------------------------- #
# Upsert helpers (cache en mémoire pour limiter les allers-retours Postgres)
# --------------------------------------------------------------------------- #

class DimCache:
    """Lookup/insert d'une valeur scalaire -> id, avec cache."""

    def __init__(self, cur: psycopg2.extensions.cursor) -> None:
        self.cur = cur
        self._pays: dict[str, int]    = {}
        self._ville: dict[tuple[str, int], int] = {}
        self._societe: dict[str, int] = {}
        self._tech: dict[str, int]    = {}
        self._langue: dict[str, int]  = {}
        self._code_cache: dict[str, dict[str, int]] = {}

    # ---- dims à code fixe (contrat/teletravail/seniorite/niveau) ----
    def by_code(self, table: str, id_col: str, code_col: str, code: str) -> int:
        if not code:
            return 0
        cache = self._code_cache.setdefault(table, {})
        if code in cache:
            return cache[code]
        self.cur.execute(
            f"SELECT {id_col} FROM analytics.{table} WHERE {code_col} = %s",
            (code,),
        )
        row = self.cur.fetchone()
        cache[code] = row[0] if row else 0
        return cache[code]

    # ---- dim_pays ----
    def pays(self, nom: str | None) -> int:
        if not nom:
            return 0
        key = nom.strip()[:128]
        if not key:
            return 0
        if key in self._pays:
            return self._pays[key]
        self.cur.execute(
            """
            INSERT INTO analytics.dim_pays (pays_nom) VALUES (%s)
            ON CONFLICT (pays_nom) DO UPDATE SET pays_nom = EXCLUDED.pays_nom
            RETURNING pays_id
            """,
            (key,),
        )
        pid = self.cur.fetchone()[0]
        self._pays[key] = pid
        return pid

    # ---- dim_ville ----
    def ville(self, nom: str | None, pays_id: int) -> int:
        if not nom:
            return 0
        key = (nom.strip()[:160], pays_id)
        if not key[0]:
            return 0
        if key in self._ville:
            return self._ville[key]
        self.cur.execute(
            """
            INSERT INTO analytics.dim_ville (ville_nom, pays_id) VALUES (%s, %s)
            ON CONFLICT (ville_nom, pays_id) DO UPDATE SET ville_nom = EXCLUDED.ville_nom
            RETURNING ville_id
            """,
            key,
        )
        vid = self.cur.fetchone()[0]
        self._ville[key] = vid
        return vid

    # ---- dim_societe ----
    def societe(self, nom: str | None) -> int:
        if not nom:
            return 0
        name = nom.strip()[:300]
        if not name:
            return 0
        if name in self._societe:
            return self._societe[name]
        slug = _slugify(name)[:300]
        self.cur.execute(
            """
            INSERT INTO analytics.dim_societe (societe_nom, societe_slug) VALUES (%s, %s)
            ON CONFLICT (societe_nom) DO UPDATE SET societe_slug = EXCLUDED.societe_slug
            RETURNING societe_id
            """,
            (name, slug),
        )
        sid = self.cur.fetchone()[0]
        self._societe[name] = sid
        return sid

    # ---- dim_technologie ----
    def tech(self, nom: str) -> int:
        key = nom.strip()[:64]
        if not key:
            return 0
        if key in self._tech:
            return self._tech[key]
        self.cur.execute(
            """
            INSERT INTO analytics.dim_technologie (tech_nom) VALUES (%s)
            ON CONFLICT (tech_nom) DO UPDATE SET tech_nom = EXCLUDED.tech_nom
            RETURNING tech_id
            """,
            (key,),
        )
        tid = self.cur.fetchone()[0]
        self._tech[key] = tid
        return tid

    # ---- dim_langue ----
    def langue(self, nom: str) -> int:
        key = nom.strip()[:32]
        if not key:
            return 0
        if key in self._langue:
            return self._langue[key]
        self.cur.execute(
            """
            INSERT INTO analytics.dim_langue (langue_nom) VALUES (%s)
            ON CONFLICT (langue_nom) DO UPDATE SET langue_nom = EXCLUDED.langue_nom
            RETURNING langue_id
            """,
            (key,),
        )
        lid = self.cur.fetchone()[0]
        self._langue[key] = lid
        return lid


# --------------------------------------------------------------------------- #
# Mapping record -> ligne fact + pivots bridge
# --------------------------------------------------------------------------- #

def _first_ville(rec: dict[str, Any]) -> str | None:
    villes = rec.get("villes") or []
    if rec.get("ville_principale"):
        return rec["ville_principale"]
    return villes[0] if villes else None


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def upsert_offer(
    cur: psycopg2.extensions.cursor,
    cache: DimCache,
    source_id: int,
    rec: dict[str, Any],
) -> int | None:
    """UPSERT une annonce, renvoie offer_id (ou None si source_ref manquant)."""

    source_ref = (rec.get("source_id") or "").strip()
    if not source_ref:
        log.warning("skip record without source_id: %s", rec.get("url"))
        return None

    # Résolution des dimensions
    pays_id    = cache.pays(rec.get("pays"))
    ville_name = _first_ville(rec)
    ville_id   = cache.ville(ville_name, pays_id)
    societe_id = cache.societe(rec.get("societe"))
    contrat_id = cache.by_code("dim_contrat",        "contrat_id",     "contrat_code",     _map_contrat(rec.get("type_contrat")))
    tele_id    = cache.by_code("dim_teletravail",    "teletravail_id", "teletravail_code", _map_teletravail(rec.get("teletravail")))
    sen_id     = cache.by_code("dim_seniorite",      "seniorite_id",   "seniorite_code",   _map_seniorite(rec.get("seniorite") or rec.get("experience_label")))
    niveau_id  = cache.by_code("dim_niveau_diplome", "niveau_id",      "niveau_code",      _map_niveau_diplome(rec.get("diplome_niveau")))

    # Dates
    date_pub_id     = _date_to_id(rec.get("date_publication") or rec.get("date_debut"), default=_SENTINEL_UNKNOWN_DATE_PUB)
    date_limite_id  = _date_to_id(rec.get("date_limite"),   default=_SENTINEL_UNKNOWN_DATE_LIMIT)
    date_scraping_id= _date_to_id(rec.get("scraped_at"),    default=_SENTINEL_UNKNOWN_DATE_PUB)

    # Mesures
    exp_min = _int(rec.get("experience_min_annees"))
    exp_max = _int(rec.get("experience_max_annees") or exp_min)
    exp_connue = (rec.get("experience_min_annees") is not None) or (rec.get("experience_max_annees") is not None)

    age_max = _int(rec.get("age_max"))
    age_connu = rec.get("age_max") is not None

    sal_min = _num(rec.get("salaire_min"))
    sal_max = _num(rec.get("salaire_max"))
    sal_connu = bool(rec.get("salaire_min") or rec.get("salaire_max"))
    devise = (rec.get("devise") or "")[:3]

    techs    = [t for t in (rec.get("technologies") or []) if t]
    missions = [m for m in (rec.get("missions") or []) if m]
    comps    = [c for c in (rec.get("competences") or []) if c]
    villes   = [v for v in (rec.get("villes") or []) if v]
    langues  = [l for l in (rec.get("langues") or []) if l]

    cur.execute(
        """
        INSERT INTO analytics.fact_offer (
            source_id, source_ref, external_id,
            societe_id, ville_id, pays_id, contrat_id, teletravail_id, seniorite_id, niveau_diplome_id,
            date_publication_id, date_limite_id, date_scraping_id,
            poste, titre_original, url, reference, statut,
            nb_postes,
            experience_min_annees, experience_max_annees, experience_connue,
            age_max, age_max_connu,
            salaire_min, salaire_max, salaire_connu, devise,
            nb_technologies, nb_missions, nb_competences, nb_villes, nb_langues,
            description_brute
        ) VALUES (
            %s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,
            %s,%s,%s,
            %s,%s,
            %s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s
        )
        ON CONFLICT (source_id, source_ref) DO UPDATE SET
            societe_id          = EXCLUDED.societe_id,
            ville_id            = EXCLUDED.ville_id,
            pays_id             = EXCLUDED.pays_id,
            contrat_id          = EXCLUDED.contrat_id,
            teletravail_id      = EXCLUDED.teletravail_id,
            seniorite_id        = EXCLUDED.seniorite_id,
            niveau_diplome_id   = EXCLUDED.niveau_diplome_id,
            date_publication_id = EXCLUDED.date_publication_id,
            date_limite_id      = EXCLUDED.date_limite_id,
            date_scraping_id    = EXCLUDED.date_scraping_id,
            poste               = EXCLUDED.poste,
            titre_original      = EXCLUDED.titre_original,
            url                 = EXCLUDED.url,
            reference           = EXCLUDED.reference,
            statut              = EXCLUDED.statut,
            nb_postes           = EXCLUDED.nb_postes,
            experience_min_annees = EXCLUDED.experience_min_annees,
            experience_max_annees = EXCLUDED.experience_max_annees,
            experience_connue   = EXCLUDED.experience_connue,
            age_max             = EXCLUDED.age_max,
            age_max_connu       = EXCLUDED.age_max_connu,
            salaire_min         = EXCLUDED.salaire_min,
            salaire_max         = EXCLUDED.salaire_max,
            salaire_connu       = EXCLUDED.salaire_connu,
            devise              = EXCLUDED.devise,
            nb_technologies     = EXCLUDED.nb_technologies,
            nb_missions         = EXCLUDED.nb_missions,
            nb_competences      = EXCLUDED.nb_competences,
            nb_villes           = EXCLUDED.nb_villes,
            nb_langues          = EXCLUDED.nb_langues,
            description_brute   = EXCLUDED.description_brute,
            updated_at          = now()
        RETURNING offer_id
        """,
        (
            source_id, source_ref, (rec.get("adzuna_id") or "")[:64],
            societe_id, ville_id, pays_id, contrat_id, tele_id, sen_id, niveau_id,
            date_pub_id, date_limite_id, date_scraping_id,
            (rec.get("poste") or "Non spécifié")[:300],
            (rec.get("titre_original") or "")[:600],
            (rec.get("url") or "")[:1000],
            (rec.get("reference") or "")[:100],
            (rec.get("statut") or "actif")[:20],
            _int(rec.get("nb_postes"), 1) or 1,
            exp_min, exp_max, exp_connue,
            age_max, age_connu,
            sal_min, sal_max, sal_connu, devise,
            len(techs), len(missions), len(comps), len(villes), len(langues),
            rec.get("description_brute") or "",
        ),
    )
    offer_id = cur.fetchone()[0]

    # Purge des enfants pour avoir un état idempotent sur re-scrape
    cur.execute("DELETE FROM analytics.bridge_offer_technologie WHERE offer_id = %s", (offer_id,))
    cur.execute("DELETE FROM analytics.bridge_offer_ville       WHERE offer_id = %s", (offer_id,))
    cur.execute("DELETE FROM analytics.bridge_offer_langue      WHERE offer_id = %s", (offer_id,))
    cur.execute("DELETE FROM analytics.bridge_offer_diplome_type WHERE offer_id = %s", (offer_id,))
    cur.execute("DELETE FROM analytics.offer_contact            WHERE offer_id = %s", (offer_id,))
    cur.execute("DELETE FROM analytics.offer_text               WHERE offer_id = %s", (offer_id,))
    cur.execute("DELETE FROM analytics.offer_geo                WHERE offer_id = %s", (offer_id,))

    # Bridges
    tech_ids = {cache.tech(t) for t in techs}
    tech_ids.discard(0)
    if tech_ids:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO analytics.bridge_offer_technologie (offer_id, tech_id) VALUES %s",
            [(offer_id, tid) for tid in tech_ids],
        )

    ville_ids = {cache.ville(v, pays_id) for v in villes}
    ville_ids.discard(0)
    if ville_ids:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO analytics.bridge_offer_ville (offer_id, ville_id) VALUES %s",
            [(offer_id, vid) for vid in ville_ids],
        )

    langue_ids = {cache.langue(l) for l in langues}
    langue_ids.discard(0)
    if langue_ids:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO analytics.bridge_offer_langue (offer_id, langue_id) VALUES %s",
            [(offer_id, lid) for lid in langue_ids],
        )

    diplome_types = {d.strip()[:120] for d in (rec.get("diplome_types") or []) if d and d.strip()}
    if diplome_types:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO analytics.bridge_offer_diplome_type (offer_id, diplome_type) VALUES %s",
            [(offer_id, d) for d in diplome_types],
        )

    # Contacts
    contacts: list[tuple[int, str, str]] = []
    for email in (rec.get("emails_contact") or []):
        if email:
            contacts.append((offer_id, "email", email[:1000]))
    for url in (rec.get("urls_postulation") or []):
        if url:
            contacts.append((offer_id, "url", url[:1000]))
    if contacts:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO analytics.offer_contact (offer_id, contact_type, valeur) VALUES %s "
            "ON CONFLICT DO NOTHING",
            contacts,
        )

    # Géoloc (Adzuna uniquement)
    if rec.get("latitude") is not None and rec.get("longitude") is not None:
        try:
            cur.execute(
                "INSERT INTO analytics.offer_geo (offer_id, latitude, longitude) VALUES (%s,%s,%s)",
                (offer_id, float(rec["latitude"]), float(rec["longitude"])),
            )
        except (TypeError, ValueError):
            pass

    # Textes libres
    text_rows: list[tuple[int, str, int, str]] = []
    for idx, m in enumerate(missions):
        text_rows.append((offer_id, "mission", idx, m))
    for idx, c in enumerate(comps):
        text_rows.append((offer_id, "competence", idx, c))
    for idx, p in enumerate(rec.get("profil") or []):
        if p:
            text_rows.append((offer_id, "profil", idx, p))
    for idx, tr in enumerate(rec.get("traits_personnalite") or []):
        if tr:
            text_rows.append((offer_id, "trait", idx, tr))
    if rec.get("culture_entreprise"):
        text_rows.append((offer_id, "culture", 0, rec["culture_entreprise"]))
    if rec.get("presentation_entreprise"):
        text_rows.append((offer_id, "presentation", 0, rec["presentation_entreprise"]))
    if rec.get("adresse"):
        text_rows.append((offer_id, "adresse", 0, rec["adresse"]))
    if text_rows:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO analytics.offer_text (offer_id, type_bloc, ordre, contenu) VALUES %s",
            text_rows,
        )

    return offer_id


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _normalize_mongo_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Les transformers supposent un format "JSON extended" (avec {$oid}, {$date})
    car ils lisent des exports raw. Ici on reçoit directement le document Mongo :
    on re-wrappe _id et scraped_at pour rester compatible sans modifier les
    transformers.
    """
    out = dict(doc)
    _id = out.get("_id")
    if _id is not None and not isinstance(_id, dict):
        out["_id"] = {"$oid": str(_id)}
    scraped = out.get("scraped_at")
    if scraped is not None and not isinstance(scraped, dict):
        if isinstance(scraped, datetime):
            out["scraped_at"] = {"$date": scraped.isoformat() + "Z"}
        else:
            out["scraped_at"] = {"$date": str(scraped)}
    return out


def _iter_source(source: str, limit: int | None) -> Iterable[dict[str, Any]]:
    cfg = SOURCES[source]
    client = MongoClient(MONGO_URI)
    col    = client[MONGO_DB][cfg["collection"]]
    cursor = col.find({})
    if limit:
        cursor = cursor.limit(limit)
    yielded = 0
    for doc in cursor:
        if not cfg["prefilter"](doc):
            continue
        yield _normalize_mongo_doc(doc)
        yielded += 1
    log.info("source=%s fetched_from_mongo=%d", source, yielded)


def run_source(pg_conn, source: str, limit: int | None) -> None:
    cfg = SOURCES[source]
    transform: Callable[[dict[str, Any]], dict[str, Any]] = cfg["transform"]
    source_id: int = cfg["source_id"]

    inserted = 0
    failed   = 0

    with pg_conn.cursor() as cur:
        cache = DimCache(cur)
        for raw in _iter_source(source, limit):
            try:
                rec = transform(raw)
                if upsert_offer(cur, cache, source_id, rec) is not None:
                    inserted += 1
                if inserted and inserted % 200 == 0:
                    pg_conn.commit()
                    log.info("source=%s commit intermédiaire (%d lignes)", source, inserted)
            except Exception:
                failed += 1
                log.exception("source=%s échec sur %s", source, raw.get("url") or raw.get("_id"))
                pg_conn.rollback()
                # Ré-ouvrir un cursor propre après rollback
                cur.close()
                cur = pg_conn.cursor()
                cache = DimCache(cur)
        pg_conn.commit()

    log.info("source=%s TERMINÉ : %d upsert, %d échecs", source, inserted, failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mongo -> Postgres ETL")
    parser.add_argument("--source", choices=list(SOURCES), default=None,
                        help="limiter à une source")
    parser.add_argument("--limit", type=int, default=None,
                        help="nombre max de documents par source (debug)")
    args = parser.parse_args()

    log.info("Connexion Postgres: %s", PG_DSN.split("@")[-1])
    with psycopg2.connect(PG_DSN) as conn:
        conn.autocommit = False
        sources = [args.source] if args.source else list(SOURCES)
        for src in sources:
            log.info(">>> Source: %s", src)
            run_source(conn, src, args.limit)

    log.info("ETL terminée.")


if __name__ == "__main__":
    main()
