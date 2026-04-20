"""
DAG: daily_jobs_pipeline
------------------------
Extract (scrapers -> MongoDB bronze) -> Transform + Load (ETL -> Postgres gold).
Runs every day at 06:00.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow"

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

    [scrape_adzuna, scrape_rekrute, scrape_emploi_public] >> load_to_postgres
