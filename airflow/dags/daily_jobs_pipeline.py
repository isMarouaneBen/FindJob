"""
DAG: daily_jobs_pipeline
------------------------
Extract (scrapers -> MongoDB bronze) -> Transform + Load (ETL -> Postgres gold)
-> embed any newly inserted offers via the FastAPI admin endpoint, which also
   flushes the recommendation cache so users see fresh results.

Runs every day at 06:00.
"""
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow"

# The platform-api container is reachable on the shared docker network as
# `platform-api:8000`. The admin token must match settings.ADMIN_TOKEN of the
# API service (set via env in docker-compose).
PLATFORM_API_URL = os.getenv("PLATFORM_API_URL", "http://platform-api:8000/api/v1")
ADMIN_TOKEN = os.getenv("PLATFORM_ADMIN_TOKEN", "local-admin-token-change-me")

default_args = {
    "owner": "job_intelligent",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="daily_jobs_pipeline",
    description="Scrape job sources and load into Postgres (daily 06:00).",
    default_args=default_args,
    start_date=datetime(2026, 4, 1),
    schedule_interval="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["jobs", "etl", "bronze", "gold"],
) as dag:

    common_env = (
        f"export PYTHONPATH={PROJECT_DIR}/scrapers:"
        f"{PROJECT_DIR}/transformers:{PROJECT_DIR}/etl && "
    )

    scrape_adzuna = BashOperator(
        task_id="scrape_adzuna",
        bash_command=common_env + f"python {PROJECT_DIR}/scrapers/adzuna_scraper.py",
    )

    scrape_rekrute = BashOperator(
        task_id="scrape_rekrute",
        bash_command=common_env + f"python {PROJECT_DIR}/scrapers/rekrute_scraper.py",
    )

    scrape_emploi_public = BashOperator(
        task_id="scrape_emploi_public",
        bash_command=common_env + f"python {PROJECT_DIR}/scrapers/emploi_public_scraper.py",
    )

    load_to_postgres = BashOperator(
        task_id="mongo_to_postgres",
        bash_command=common_env + f"python {PROJECT_DIR}/etl/mongo_to_postgres.py",
    )

    # Embed offers without an embedding + invalidate the reco cache.
    # The endpoint is idempotent — if nothing's pending it returns {embedded:0}.
    # Long timeout because first-run with no embeddings can take a few minutes.
    embed_new_offers = BashOperator(
        task_id="embed_new_offers",
        bash_command=(
            f"curl -sS -X POST '{PLATFORM_API_URL}/admin/embed-offers' "
            f"-H 'X-Admin-Token: {ADMIN_TOKEN}' "
            "-H 'Content-Type: application/json' "
            "--max-time 1800 "  # 30 min hard cap
            "-w '\\nHTTP %{http_code}\\n' "
            "| tee /tmp/embed_result.json && "
            "grep -q '\"embedded\"' /tmp/embed_result.json"
        ),
    )

    [scrape_adzuna, scrape_rekrute, scrape_emploi_public] >> load_to_postgres >> embed_new_offers
