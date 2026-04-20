"""
=====================================================
 PROJET JOB INTELLIGENT — Scraper Emploi-public.ma
 Bronze Layer : stockage brut dans MongoDB
 v5 : structure HTML corrigée après analyse du HTML réel
      - conteneur : div.s-item
      - lien       : a.card.card-scale
      - pagination : ?key_word=data&page=N (11 pages)
=====================================================
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
import requests

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
from io import BytesIO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError
import PyPDF2

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
MONGO_URI        = os.getenv("MONGO_URI", "mongodb://admin:admin123@localhost:27017/")
MONGO_DB         = "job_raw"
MONGO_COLLECTION = "emploi_public_raw"

BASE_URL         = "https://www.emploi-public.ma"
LIST_URL         = f"{BASE_URL}/fr/concours-liste"
KEYWORD          = "data"
MAX_PAGES        = 1     # TEST : 1 page seulement
DELAY_BETWEEN_PAGES = 2  # secondes entre chaque page

# ─────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "emploi_public_scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
#  DRIVER SELENIUM
# ─────────────────────────────────────────
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # Selenium Manager (intégré à selenium >= 4.11) résout automatiquement
    # le chromedriver correspondant à la version de Chrome installée.
    driver = webdriver.Chrome(options=options)
    return driver


# ─────────────────────────────────────────
#  EXTRACTION DNS PDF
# ─────────────────────────────────────────
def extract_pdf_text_from_url(pdf_url):
    """
    Télécharge un PDF à partir d'une URL et extrait le texte.
    """
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(pdf_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        pdf_file = BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
        
        logger.info(f"PDF extrait avec succès — {len(text)} caractères.")
        return text.strip() if text.strip() else None
    except Exception as e:
        logger.error(f"Erreur extraction PDF {pdf_url} : {e}")
        return None


def get_pdf_description(driver, offre_url):
    """
    Navigue vers la page détail de l'offre et extrait le PDF.
    Cherche le lien <a class="s-content-box btn bg-blue">
    """
    try:
        logger.info(f"Navigation vers détail : {offre_url}")
        driver.get(offre_url)
        
        # Attendre que la page se charge
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "s-content-box"))
        )
        
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        # Chercher le lien PDF : <a class="s-content-box btn bg-blue">
        pdf_link = soup.find("a", class_=lambda c: c and "s-content-box" in c and "btn" in c)
        
        if not pdf_link:
            logger.warning(f"Pas de lien PDF trouvé sur {offre_url}")
            return None
        
        pdf_url = pdf_link.get("href", "")
        if not pdf_url:
            logger.warning(f"Attribut href vide sur {offre_url}")
            return None
        
        # Convertir URL relative en absolue si nécessaire
        if not pdf_url.startswith("http"):
            pdf_url = BASE_URL + pdf_url
        
        logger.info(f"URL PDF détectée : {pdf_url}")
        
        # Télécharger et extraire le texte du PDF
        pdf_text = extract_pdf_text_from_url(pdf_url)
        return pdf_text
    except TimeoutException:
        logger.warning(f"Timeout lors de l'accès à {offre_url}")
        return None
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction PDF de {offre_url} : {e}")
        return None


# ─────────────────────────────────────────
#  PARSING — Une carte offre
# ─────────────────────────────────────────
def parse_card(item):
    """
    Extrait les données d'un <div class="s-item">.

    Structure HTML réelle :
      div.s-item
        └── a.card.card-scale [href → URL détail]
              ├── div.card-body
              │     ├── h2.card-title        → titre
              │     ├── div.card-text        → société
              │     └── div.card--btn
              │           └── div.card-type  → type annonce
              └── div.card-footer
                    ├── div[0]               → nombre de postes
                    └── div[1]               → date limite
    """
    offre = {
        "source":       "emploi_public",
        "scraped_at":   datetime.now(timezone.utc),
        "titre":        None,
        "societe":      None,
        "nb_postes":    None,
        "date_limite":  None,
        "type_annonce": None,
        "url":          None,
        "description":  None,
        "statut":       "actif",
    }

    # ── URL : lien principal de la carte
    a_tag = item.find("a", class_=lambda c: c and "card" in c and "card-scale" in c)
    if not a_tag:
        return None

    href = a_tag.get("href", "")
    offre["url"] = href if href.startswith("http") else BASE_URL + href

    # ── Titre
    h2 = a_tag.find("h2", class_="card-title")
    if h2:
        offre["titre"] = h2.get_text(strip=True)

    # ── Société
    card_text = a_tag.find("div", class_="card-text")
    if card_text:
        # Enlever l'icône et ne garder que le texte
        offre["societe"] = card_text.get_text(strip=True)

    # ── Type annonce (Annonce / Résultat / Convocation)
    type_div = a_tag.find("div", class_=lambda c: c and "card-type" in c)
    if type_div:
        offre["type_annonce"] = type_div.get_text(strip=True)

    # ── Footer : nb_postes + date_limite
    footer = a_tag.find("div", class_="card-footer")
    if footer:
        footer_divs = footer.find_all("div", recursive=False)
        if len(footer_divs) >= 1:
            offre["nb_postes"]   = footer_divs[0].get_text(strip=True)
        if len(footer_divs) >= 2:
            offre["date_limite"] = footer_divs[1].get_text(strip=True)

    return offre if offre["titre"] else None


# ─────────────────────────────────────────
#  PARSING — Page complète
# ─────────────────────────────────────────
def parse_page(html):
    """
    Parse tous les div.s-item d'une page.
    """
    offres = []
    soup   = BeautifulSoup(html, "html.parser")

    # Conteneur principal de la liste
    listing = soup.find("div", id="listing-switcher")
    if not listing:
        logger.warning("Conteneur #listing-switcher introuvable.")
        return offres

    items = listing.find_all("div", class_=lambda c: c and "s-item" in c)
    logger.info(f"  → {len(items)} offres trouvées sur cette page.")

    for item in items:
        try:
            offre = parse_card(item)
            if offre:
                offres.append(offre)
        except Exception as e:
            logger.error(f"Erreur parsing carte : {e}")
            continue

    return offres


# ─────────────────────────────────────────
#  SCRAPING — Toutes les pages avec Selenium
# ─────────────────────────────────────────
def scrape_all_pages(driver):
    """
    Scrape toutes les pages de résultats.
    Pagination : ?key_word=data&page=N
    Pour chaque offre trouvée, extrait aussi le contenu PDF.
    """
    all_offres = []

    for page_num in range(1, MAX_PAGES + 1):
        url = f"{LIST_URL}?key_word={KEYWORD}&page={page_num}"
        logger.info(f"Scraping page {page_num}/{MAX_PAGES} — {url}")

        driver.get(url)

        # Attendre que les cartes soient chargées
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s-item"))
            )
        except TimeoutException:
            logger.warning(f"Page {page_num} — timeout, aucune carte détectée. Arrêt.")
            break

        html   = driver.page_source
        offres = parse_page(html)

        if not offres:
            logger.info(f"Page {page_num} vide — fin de pagination.")
            break

        # Pour chaque offre, extraire la description PDF
        for offre in offres:
            if offre.get("url"):
                logger.info(f"Extraction PDF pour : {offre['titre']}")
                description = get_pdf_description(driver, offre["url"])
                offre["description"] = description
                time.sleep(1)  # Délai entre chaque extraction PDF

        all_offres.extend(offres)
        logger.info(f"Total cumulé : {len(all_offres)} offres.")
        time.sleep(DELAY_BETWEEN_PAGES)

    return all_offres


# ─────────────────────────────────────────
#  CONNEXION MONGODB
# ─────────────────────────────────────────
def get_mongo_collection():
    client = MongoClient(MONGO_URI)
    col    = client[MONGO_DB][MONGO_COLLECTION]
    # URL unique comme clé de déduplication
    col.create_index("url", unique=True)
    logger.info("Connexion MongoDB établie.")
    return col


# ─────────────────────────────────────────
#  SAUVEGARDE MongoDB
# ─────────────────────────────────────────
def save_to_mongo(offres, collection):
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
    logger.info("Démarrage du scraper Emploi-public.ma v5")
    logger.info("=" * 50)

    driver     = get_driver()
    collection = get_mongo_collection()

    try:
        offres = scrape_all_pages(driver)
        logger.info(f"Scraping terminé — {len(offres)} offres extraites.")
        save_to_mongo(offres, collection)
        logger.info("Sauvegarde MongoDB terminée.")
    finally:
        driver.quit()
        logger.info("Driver Selenium fermé.")


if __name__ == "__main__":
    main()