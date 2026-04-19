"""
=====================================================
 PROJET JOB INTELLIGENT — Scraper Adzuna API (France)
 Domaine : Data
 Bronze Layer : stockage brut dans MongoDB
=====================================================
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
LOG_DIR  = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
load_dotenv(dotenv_path=ENV_PATH)

ADZUNA_APP_ID  = os.getenv("ADZUNA_APP_ID", "").strip()
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY", "").strip()

MONGO_URI        = "mongodb://admin:admin123@localhost:27017/"
MONGO_DB         = "job_raw"
MONGO_COLLECTION = "adzuna_raw"

ADZUNA_COUNTRY = "fr"
ADZUNA_BASE    = f"https://api.adzuna.com/v1/api/jobs/{ADZUNA_COUNTRY}/search"

# Mots-clés "data" — l'API combine en OR via le champ "what_or"
DATA_KEYWORDS = (
    "data scientist data engineer data analyst "
    "machine learning big data analytics"
)

RESULTS_PER_PAGE       = 50
MAX_PAGES              = 20
DELAY_BETWEEN_REQUESTS = 1  # secondes

# ─────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "adzuna_scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
#  CONNEXION MONGODB
# ─────────────────────────────────────────
def get_mongo_collection():
    client = MongoClient(MONGO_URI)
    col    = client[MONGO_DB][MONGO_COLLECTION]
    col.create_index("adzuna_id", unique=True)
    logger.info("Connexion MongoDB établie.")
    return col


# ─────────────────────────────────────────
#  APPEL API
# ─────────────────────────────────────────
def fetch_page(session, page_num):
    """
    Interroge l'API Adzuna pour une page donnée.
    Retourne la liste des offres (brutes) ou [] si erreur / fin.
    """
    url = f"{ADZUNA_BASE}/{page_num}"
    params = {
        "app_id":           ADZUNA_APP_ID,
        "app_key":          ADZUNA_API_KEY,
        "results_per_page": RESULTS_PER_PAGE,
        "what_or":          DATA_KEYWORDS,
        "content-type":     "application/json",
    }

    try:
        resp = session.get(url, params=params, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Erreur requête page {page_num} : {e}")
        return []

    payload = resp.json()
    return payload.get("results", [])


# ─────────────────────────────────────────
#  NORMALISATION
# ─────────────────────────────────────────
def normalize_offer(raw):
    """
    Transforme la réponse brute Adzuna en un document prêt pour MongoDB.
    On conserve l'intégralité de la charge brute dans `raw` pour la couche Bronze.
    """
    return {
        "source":         "adzuna",
        "scraped_at":     datetime.now(timezone.utc),
        "adzuna_id":      str(raw.get("id")) if raw.get("id") else None,
        "titre":          raw.get("title"),
        "url":            raw.get("redirect_url"),
        "description":    raw.get("description"),
        "entreprise":     (raw.get("company") or {}).get("display_name"),
        "localisation":   (raw.get("location") or {}).get("display_name"),
        "location_area":  (raw.get("location") or {}).get("area"),
        "categorie":      (raw.get("category") or {}).get("label"),
        "contract_type":  raw.get("contract_type"),
        "contract_time":  raw.get("contract_time"),
        "salaire_min":    raw.get("salary_min"),
        "salaire_max":    raw.get("salary_max"),
        "devise":         raw.get("salary_is_predicted"),
        "created":        raw.get("created"),
        "latitude":       raw.get("latitude"),
        "longitude":      raw.get("longitude"),
        "statut":         "actif",
        "raw":            raw,
    }


# ─────────────────────────────────────────
#  SCRAPING
# ─────────────────────────────────────────
def scrape_adzuna(session, max_pages=MAX_PAGES):
    all_offres = []

    for page_num in range(1, max_pages + 1):
        logger.info(f"Adzuna — récupération page {page_num}/{max_pages}")
        raw_results = fetch_page(session, page_num)

        if not raw_results:
            logger.info(f"Page {page_num} vide — fin de pagination.")
            break

        offres = [normalize_offer(r) for r in raw_results if r.get("id")]
        logger.info(f"  → {len(offres)} offres extraites.")
        all_offres.extend(offres)

        if len(raw_results) < RESULTS_PER_PAGE:
            logger.info("Dernière page atteinte.")
            break

        time.sleep(DELAY_BETWEEN_REQUESTS)

    return all_offres


# ─────────────────────────────────────────
#  SAUVEGARDE MongoDB
# ─────────────────────────────────────────
def save_to_mongo(offres, collection):
    if not offres:
        logger.warning("Aucune offre à sauvegarder.")
        return

    operations = [
        UpdateOne(
            {"adzuna_id": offre["adzuna_id"]},
            {"$set": offre},
            upsert=True,
        )
        for offre in offres
        if offre.get("adzuna_id")
    ]

    try:
        result = collection.bulk_write(operations, ordered=False)
        logger.info(
            f"MongoDB — insérés : {result.upserted_count} | "
            f"mis à jour : {result.modified_count}"
        )
    except BulkWriteError as e:
        logger.error(f"Erreur bulk write : {e.details}")


# ─────────────────────────────────────────
#  POINT D'ENTRÉE
# ─────────────────────────────────────────
def main():
    logger.info("=" * 50)
    logger.info("Démarrage du scraper Adzuna (France / Data)")
    logger.info("=" * 50)

    if not ADZUNA_APP_ID or not ADZUNA_API_KEY:
        logger.error(
            "Identifiants Adzuna manquants dans .env "
            "(ADZUNA_APP_ID / ADZUNA_API_KEY)."
        )
        return

    session = requests.Session()
    collection = get_mongo_collection()

    offres = scrape_adzuna(session, max_pages=MAX_PAGES)
    logger.info(f"Scraping terminé — {len(offres)} offres extraites.")

    save_to_mongo(offres, collection)
    logger.info("Sauvegarde MongoDB terminée.")


if __name__ == "__main__":
    main()
