"""
=====================================================
 PROJET JOB INTELLIGENT — Scraper Rekrute.com
 Bronze Layer : stockage brut dans MongoDB
 v2 : ajout parsing page détail de chaque offre
=====================================================
"""

import time
import logging
from pathlib import Path
from datetime import datetime, timezone

import requests

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
from bs4 import BeautifulSoup
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
MONGO_URI        = "mongodb://admin:admin123@localhost:27017/"
MONGO_DB         = "job_raw"
MONGO_COLLECTION = "rekrute_raw"

BASE_URL         = "https://www.rekrute.com"
SEARCH_URL       = f"{BASE_URL}/offres.html"

SEARCH_PARAMS = {
    "s": 3,
    "lang": 1,
    "keyword": "data",
}

MAX_PAGES               = 10
DELAY_BETWEEN_REQUESTS  = 2   # secondes entre chaque requête

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# ─────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "rekrute_scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
#  CONNEXION MONGODB
# ─────────────────────────────────────────
def get_mongo_collection():
    client = MongoClient(MONGO_URI)
    col    = client[MONGO_DB][MONGO_COLLECTION]
    col.create_index("url", unique=True)
    logger.info("Connexion MongoDB établie.")
    return col


# ─────────────────────────────────────────
#  PARSING — Page liste
# ─────────────────────────────────────────
def parse_list_page(soup):
    """
    Extrait titre + url + dates depuis la page liste.
    Retourne une liste de dicts partiels.
    """
    offres    = []
    post_list = soup.find("ul", id="post-data")

    if not post_list:
        logger.warning("Aucune liste d'offres trouvée sur cette page.")
        return offres

    items = post_list.find_all("li", class_="post-id")
    logger.info(f"  → {len(items)} offres trouvées sur cette page.")

    for item in items:
        try:
            offre = parse_single_post(item)
            if offre:
                offres.append(offre)
        except Exception as e:
            logger.error(f"Erreur parsing post liste : {e}")
            continue

    return offres


def parse_single_post(li):
    """
    Extrait les données de base d'un <li class="post-id"> :
    titre, url, date_debut, date_limite.
    """
    offre = {
        "source":       "rekrute",
        "scraped_at":   datetime.now(timezone.utc),
        "titre":        None,
        "url":          None,
        "date_debut":   None,
        "date_limite":  None,
        "statut":       "actif",
    }

    col_div = li.find("div", class_=lambda c: c and "col-sm-10" in c)
    if not col_div:
        return None

    # ── Titre + URL
    section_div = col_div.find("div", class_="section")
    if section_div:
        h2 = section_div.find("h2")
        if h2:
            a_tag = h2.find("a", class_="titreJob")
            if a_tag:
                offre["titre"] = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")
                offre["url"] = href if href.startswith("http") else BASE_URL + href

    # ── Dates depuis la page liste
    holder_div = col_div.find("div", class_="holder")
    if holder_div:
        em_date = holder_div.find("em", class_="date")
        if em_date:
            spans = em_date.find_all("span")
            if len(spans) >= 1:
                offre["date_debut"]  = spans[0].get_text(strip=True)
            if len(spans) >= 2:
                offre["date_limite"] = spans[1].get_text(strip=True)

    return offre if offre["url"] else None


# ─────────────────────────────────────────
#  PARSING — Page détail d'une offre
# ─────────────────────────────────────────
def parse_detail_page(soup):
    """
    Extrait les détails complets depuis la page d'une offre :
      - infos      : dict {title_li: texte_li} depuis les deux ul.featureInfo
      - description: texte condensé depuis les div.col-md-12.blc
    """
    details = {
        "infos":       {},
        "description": None,
    }

    # ── INFOS : div.listWrpService.jobdetail > div.row > ul.featureInfo
    wrapper = soup.find("div", class_=lambda c: c and "listWrpService" in c and "jobdetail" in c)
    if wrapper:
        row_div = wrapper.find("div", class_="row")
        if row_div:
            feature_lists = row_div.find_all("ul", class_="featureInfo")
            for ul in feature_lists:
                for li in ul.find_all("li"):
                    # title de la <li> = clé, texte de la <li> = valeur
                    cle    = li.get("title", "").strip()
                    valeur = li.get_text(strip=True)
                    if cle and valeur:
                        # Normaliser la clé : minuscules, underscores
                        cle_norm = cle.lower().replace(" ", "_").replace("'", "").replace("-", "_")
                        details["infos"][cle_norm] = valeur

    # ── DESCRIPTION : tous les div.col-md-12.blc
    blc_divs = soup.find_all(
        "div",
        class_=lambda c: c and "col-md-12" in c and "blc" in c
    )
    description_parts = []
    for blc in blc_divs:
        # Extraire tout le texte (h2 + ul > li) comme plain text
        texte = blc.get_text(separator=" ", strip=True)
        if texte:
            description_parts.append(texte)

    if description_parts:
        details["description"] = " | ".join(description_parts)

    return details


# ─────────────────────────────────────────
#  SCRAPING — Toutes les pages + détails
# ─────────────────────────────────────────
def scrape_rekrute(session, max_pages=MAX_PAGES):
    """
    Scrape la liste des offres page par page,
    puis visite chaque page détail pour enrichir les données.
    """
    all_offres = []

    for page_num in range(1, max_pages + 1):
        params = {**SEARCH_PARAMS, "p": page_num}
        logger.info(f"Scraping page liste {page_num}/{max_pages}")

        try:
            response = session.get(SEARCH_URL, params=params, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Erreur requête page liste {page_num} : {e}")
            break

        soup   = BeautifulSoup(response.text, "html.parser")
        offres = parse_list_page(soup)

        if not offres:
            logger.info(f"Page {page_num} vide — fin de pagination.")
            break

        # ── Pour chaque offre, récupérer la page détail
        for i, offre in enumerate(offres):
            url_detail = offre.get("url")
            if not url_detail:
                continue

            logger.info(f"    Détail {i+1}/{len(offres)} : {offre['titre']}")
            try:
                resp_detail = session.get(url_detail, timeout=15)
                resp_detail.raise_for_status()
                soup_detail = BeautifulSoup(resp_detail.text, "html.parser")
                details     = parse_detail_page(soup_detail)
                offre.update(details)
            except requests.RequestException as e:
                logger.warning(f"    Impossible de charger le détail : {e}")

            time.sleep(DELAY_BETWEEN_REQUESTS)

        all_offres.extend(offres)
        logger.info(f"Total cumulé : {len(all_offres)} offres.")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    return all_offres


# ─────────────────────────────────────────
#  SAUVEGARDE MongoDB
# ─────────────────────────────────────────
def save_to_mongo(offres, collection):
    """
    Upsert dans MongoDB sur l'URL comme clé unique.
    """
    if not offres:
        logger.warning("Aucune offre à sauvegarder.")
        return

    operations = [
        UpdateOne(
            {"url": offre["url"]},
            {"$set": offre},
            upsert=True
        )
        for offre in offres
        if offre.get("url")
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
    logger.info("Démarrage du scraper Rekrute v2")
    logger.info("=" * 50)

    session = requests.Session()
    session.headers.update(HEADERS)

    collection = get_mongo_collection()
    offres     = scrape_rekrute(session, max_pages=MAX_PAGES)

    logger.info(f"Scraping terminé — {len(offres)} offres extraites.")
    save_to_mongo(offres, collection)
    logger.info("Sauvegarde MongoDB terminée.")


if __name__ == "__main__":
    main()