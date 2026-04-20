# ==============================================================
#  Image Airflow custom — Projet Job Intelligent
#  Base : apache/airflow:2.8.1
#  Ajouts :
#    - Google Chrome stable + dépendances système
#    - Packages Python requis par scrapers/ transformers/ etl/
# ==============================================================
FROM apache/airflow:2.8.1

USER root

# --------------------------------------------------------------
# Dépendances système + Google Chrome stable
# Chromedriver est géré automatiquement par Selenium Manager
# (selenium >= 4.11) donc pas besoin de l'installer ici.
# --------------------------------------------------------------
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        fonts-liberation \
        libasound2 \
        libnss3 \
        libxss1 \
        libappindicator3-1 \
        libatk-bridge2.0-0 \
        libgtk-3-0 \
        libgbm1 \
        xdg-utils \
 && wget -q -O /tmp/google-chrome.deb \
        https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
 && apt-get install -y --no-install-recommends /tmp/google-chrome.deb \
 && rm -f /tmp/google-chrome.deb \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

USER airflow

# --------------------------------------------------------------
# Dépendances Python
# --------------------------------------------------------------
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
