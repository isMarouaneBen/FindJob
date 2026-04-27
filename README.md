# FindJob — Intelligent Job Aggregation ETL Platform

<div align="center">

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-3.8-blue.svg)](https://www.docker.com/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.8-017CEE.svg)](https://airflow.apache.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green.svg)](https://www.mongodb.com/)

**A production-grade data pipeline that aggregates, transforms, and analyzes job listings from multiple sources across France and Morocco.**

[Overview](#overview) • [Features](#features) • [Architecture](#architecture) • [Quick Start](#quick-start) • [Configuration](#configuration) • [Development](#development)

</div>

---

## Overview

**FindJob** is an end-to-end ETL (Extract, Transform, Load) platform designed to:

- **Aggregate** job listings from three major sources: Adzuna (France), ReKrute (Morocco), and Emploi-Public.ma (Morocco)
- **Standardize** heterogeneous data into a unified schema with salary estimation
- **Enrich** raw job postings with NLP-based skill and requirement extraction
- **Analyze** job market trends via a dimensional data warehouse (star schema)
- **Automate** daily data refresh cycles using Apache Airflow orchestration

The platform implements a **medallion architecture** (Bronze → Silver → Gold) with:
- **MongoDB** as the Bronze layer (raw ingestion)
- **PostgreSQL** as the Silver/Gold layers (transformed, analytics-ready data)

Perfect for market researchers, data analysts, and job market intelligence applications.

---

## Features

### 🗂️ Data Aggregation
- **Multi-source scraping**: Adzuna API, ReKrute web scraper, Emploi-Public.ma (Selenium automation)
- **Real-time ingestion**: Three independent parallel scrapers
- **Robust error handling**: Retry logic, rate limiting, malformed data detection

### 🔄 Data Transformation
- **Salary estimation**: Machine-learning-based salary range prediction for jobs without explicit salary data
- **NLP normalization**: Skill extraction, technology detection, role classification
- **Geolocation enrichment**: City and country standardization across sources
- **Multi-language support**: French and Arabic text processing

### 📊 Analytics-Ready Schema
- **Star schema**: 1 fact table + 9 dimension tables (Kimball methodology)
- **Pre-aggregated metrics**: Denormalized data for fast BI queries
- **Technology bridge table**: Many-to-many relationship between offers and required skills
- **Temporal dimensions**: Date hierarchy (year/quarter/month/day)

### ⚙️ Orchestration & Monitoring
- **Daily automation**: Scheduled DAGs (6:00 AM UTC daily)
- **Fault tolerance**: Automatic retries with configurable backoff
- **Comprehensive logging**: Structured logs for each pipeline stage
- **Web UI monitoring**: Airflow WebUI for DAG visualization and health checks

### 🛡️ Data Quality
- **Deduplication**: UPSERT operations prevent duplicate job postings
- **Type validation**: Consistent data types across all layers
- **Referential integrity**: Foreign key constraints in PostgreSQL
- **Audit trails**: Timestamp tracking for ingestion and transformation

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │
│  │  Adzuna    │  │  ReKrute   │  │ Emploi-Public.ma   │    │
│  │   API      │  │  Web       │  │  Selenium + API    │    │
│  │  (France)  │  │  Scraper   │  │  (Morocco)         │    │
│  │            │  │ (Morocco)  │  │                    │    │
│  └────────────┘  └────────────┘  └────────────────────┘    │
└────────┬────────────────┬──────────────────────┬────────────┘
         │                │                      │
         └─────────────────┼──────────────────────┘
                    (3 parallel tasks)
                           │
                           ▼
        ┌──────────────────────────────────┐
        │        AIRFLOW ORCHESTRATOR       │
        │   daily_jobs_pipeline (06:00 UTC)│
        └──────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
        ▼                                     ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│     MONGODB (BRONZE)     │      │   TRANSFORMERS (SILVER)  │
│ ┌──────────────────────┐ │      │ ┌────────────────────┐   │
│ │ adzuna_raw           │ │      │ │ adzuna_transformer │   │
│ │ emploi_public_raw    │ │ ───► │ │ rekrute_transformer│   │
│ │ rekrute_raw          │ │      │ │ emploi_transformer │   │
│ └──────────────────────┘ │      │ │ salary_estimator   │   │
│  Raw JSON documents     │      │ └────────────────────┘   │
└──────────────────────────┘      └──────────────────────────┘
                                            │
                                            ▼
                                ┌──────────────────────────┐
                                │  POSTGRESQL (GOLD)       │
                                │ ┌────────────────────┐   │
                                │ │ FACT TABLE:        │   │
                                │ │ fact_offer (jobs)  │   │
                                │ ├────────────────────┤   │
                                │ │ DIMENSIONS:        │   │
                                │ │ • dim_source       │   │
                                │ │ • dim_pays         │   │
                                │ │ • dim_ville        │   │
                                │ │ • dim_societe      │   │
                                │ │ • dim_contrat      │   │
                                │ │ • dim_teletravail  │   │
                                │ │ • dim_seniorite    │   │
                                │ │ • dim_diplome      │   │
                                │ │ • dim_technologie  │   │
                                │ │ • dim_date         │   │
                                │ └────────────────────┘   │
                                │  Analytics-ready data    │
                                └──────────────────────────┘
```

### Pipeline Layers

| Layer | Technology | Purpose | Format |
|-------|-----------|---------|--------|
| **Bronze** | MongoDB | Raw job data ingestion | JSON documents (unmodified) |
| **Silver** | Python transformers | Data cleaning & standardization | Validated Python dicts |
| **Gold** | PostgreSQL star schema | Analytics & reporting | Normalized dimensional tables |

### Data Flow

```
1. EXTRACT (Scraping)
   ├─ adzuna_scraper.py      → fetch from Adzuna API (50 results/page, max 1000)
   ├─ rekrute_scraper.py     → fetch from ReKrute search pages
   └─ emploi_public_scraper.py → fetch + parse with Selenium + PDF parsing

2. LOAD (Bronze)
   ├─ Upsert into MongoDB collections (one per source)
   ├─ Deduplication via job ID
   └─ Raw data preservation (audit trail)

3. TRANSFORM (Silver)
   ├─ Load from MongoDB collections
   ├─ Apply source-specific transformers (normalization, enrichment)
   ├─ Estimate salaries (if missing)
   ├─ Extract technologies and skills
   └─ Standardize to common schema

4. LOAD (Gold)
   ├─ Upsert into PostgreSQL fact_offer table
   ├─ Populate dimension tables (slow-change dimension)
   ├─ Create bridge table relationships (technologies)
   └─ Maintain referential integrity
```

---

## Quick Start

### Prerequisites

- **Docker Desktop** (v4.20+) with Docker Compose
- **Git** for repository cloning
- **~4 GB** free disk space
- **Windows/Mac/Linux** with WSL2 (on Windows)

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/findjob.git
   cd findjob
   ```

2. **Create environment file (`.env`):**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your credentials:
   ```env
   # API Keys (get from Adzuna Developer Portal)
   ADZUNA_APP_ID=your_app_id
   ADZUNA_API_KEY=your_api_key

   # Database URLs (pre-configured in docker-compose.yml)
   MONGO_URI=mongodb://admin:admin123@mongodb:27017/
   POSTGRES_DATA_URI=postgresql://datauser:datapass@postgres:5433/job_db

   # Airflow admin credentials
   AIRFLOW_ADMIN_USER=admin
   AIRFLOW_ADMIN_PASSWORD=admin123
   AIRFLOW_ADMIN_EMAIL=admin@jobintelligent.ma
   ```

3. **Start the stack:**
   ```bash
   docker-compose up -d
   ```

4. **Initialize Airflow:**
   ```bash
   docker-compose exec airflow airflow db init
   docker-compose exec airflow airflow users create \
     --role Admin \
     --username admin \
     --email admin@jobintelligent.ma \
     --firstname Admin \
     --lastname User \
     --password admin123
   ```

5. **Access the services:**
   - **Airflow WebUI**: http://localhost:8080 (admin/admin123)
   - **pgAdmin**: http://localhost:5050 (admin@jobintelligent.ma/admin123)
   - **PostgreSQL**: localhost:5433 (user: datauser, password: datapass)
   - **MongoDB**: localhost:27017 (user: admin, password: admin123)

6. **Trigger the DAG:**
   ```bash
   # Manual trigger
   docker-compose exec airflow airflow dags trigger daily_jobs_pipeline
   
   # Check logs
   docker-compose exec airflow airflow dags test daily_jobs_pipeline
   ```

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ADZUNA_APP_ID` | Adzuna API application ID | (none) | ✅ Yes |
| `ADZUNA_API_KEY` | Adzuna API authentication key | (none) | ✅ Yes |
| `MONGO_URI` | MongoDB connection string | `mongodb://admin:admin123@localhost:27017/` | ❌ No |
| `MONGO_DB` | MongoDB database name | `job_raw` | ❌ No |
| `POSTGRES_DATA_URI` | PostgreSQL analytics connection | `postgresql://datauser:datapass@localhost:5433/job_db` | ❌ No |
| `AIRFLOW_HOME` | Airflow base directory | `/opt/airflow` | ❌ No |

### Airflow Configuration

Key DAG settings (in `airflow/dags/daily_jobs_pipeline.py`):

```python
schedule_interval="0 6 * * *",      # Daily at 06:00 UTC
max_active_runs=1,                   # Prevent concurrent runs
retries=2,                           # Retry failed tasks 2x
retry_delay=timedelta(minutes=5),    # Wait 5 min between retries
```

### Scraper Configuration

#### Adzuna Scraper (`scrapers/adzuna_scraper.py`)

```python
DATA_KEYWORDS = "data scientist data engineer data analyst machine learning big data"
ADZUNA_COUNTRY = "fr"         # France
RESULTS_PER_PAGE = 50         # API pagination size
MAX_PAGES = 20                # Max 1000 results per run
DELAY_BETWEEN_REQUESTS = 1    # Rate limiting (seconds)
```

#### ReKrute Scraper (`scrapers/rekrute_scraper.py`)

```python
REKRUTE_BASE_URL = "https://www.rekrute.com"
SEARCH_KEYWORDS = "data scientist data engineer"
PAGINATION_SIZE = 50
```

#### Emploi-Public Scraper (`scrapers/emploi_public_scraper.py`)

```python
EMPLOI_PUBLIC_BASE_URL = "https://www.emploi-public.ma"
HEADLESS_BROWSER = True       # Run Selenium in headless mode
PDF_PARSING = True            # Extract PDF job descriptions
```

### Salary Estimation Rules

The `salary_estimator.py` uses role-based lookup with fallback adjustments:

```python
# Example rules (in MAD - Moroccan Dirhams)
ROLE_SALARY_MAD = {
    "data scientist": (18000, 35000),    # Monthly gross
    "data engineer": (17000, 32000),
    "data analyst": (12000, 25000),
    "junior": (-30%),                    # Seniority adjustment
    "senior": (+20%),
}
```

Estimates can be overridden by setting `salary_min` / `salary_max` in MongoDB.

---

## Development

### Project Structure

```
findjob/
├── airflow/
│   ├── dags/
│   │   └── daily_jobs_pipeline.py    # Main orchestration DAG
│   ├── logs/                         # DAG execution logs
│   ├── plugins/                      # Airflow plugins (custom operators)
│   ├── requirements.txt              # Airflow + Python dependencies
│   └── Dockerfile                    # Airflow image build
│
├── scrapers/                         # Bronze layer (ingestion)
│   ├── adzuna_scraper.py
│   ├── rekrute_scraper.py
│   ├── emploi_public_scraper.py
│   └── requirements.txt
│
├── transformers/                     # Silver layer (cleaning)
│   ├── adzuna_transformer.py
│   ├── rekrute_transformer.py
│   ├── emploi_public_transformer.py
│   └── salary_estimator.py
│
├── etl/
│   └── mongo_to_postgres.py          # Gold layer (load to analytics DB)
│
├── data/
│   ├── raw/                          # Local raw data samples
│   └── data/                         # Local cleaned data samples
│
├── dashboard/
│   ├── Revenue and Profitability.json # Power BI model
│   └── power bi dashboard.fig        # Power BI dashboard
│
├── postgres-init/
│   └── init-schema.sql               # PostgreSQL star schema
│
├── mongo-init/                       # MongoDB initialization (optional)
│   └── init.js
│
├── db_snapshot/
│   └── data_snapshot.dump            # PostgreSQL backup
│
├── docker-compose.yml                # Services orchestration
├── .env.example                      # Environment template
├── README.md                         # This file
└── pass.txt                          # Credentials reference
```

### Running Locally (Without Docker)

#### 1. Set up Python environment:
```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r airflow/requirements.txt
pip install -r scrapers/requirements.txt
```

#### 2. Start MongoDB & PostgreSQL:
```bash
# Using local installations or Docker
docker run -d -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=admin123 mongo:7.0
docker run -d -p 5433:5432 -e POSTGRES_PASSWORD=datapass postgres:16
```

#### 3. Initialize PostgreSQL schema:
```bash
psql -h localhost -p 5433 -U postgres < postgres-init/init-schema.sql
```

#### 4. Run individual scrapers:
```bash
python scrapers/adzuna_scraper.py
python scrapers/rekrute_scraper.py
python scrapers/emploi_public_scraper.py
```

#### 5. Run ETL transformation:
```bash
python etl/mongo_to_postgres.py --source adzuna
python etl/mongo_to_postgres.py --source rekrute
python etl/mongo_to_postgres.py --source emploi_public
```

### Testing & Validation

#### Unit Tests
```bash
# Run scraper tests
python -m pytest scrapers/test_*.py -v

# Run transformer tests
python -m pytest transformers/test_*.py -v

# Run ETL tests
python -m pytest etl/test_*.py -v
```

#### Data Quality Checks
```bash
# Verify PostgreSQL schema
psql -h localhost -p 5433 -U datauser -d job_db -c "\dt analytics.*"

# Count records by source
psql -h localhost -p 5433 -U datauser -d job_db -c \
  "SELECT source_id, COUNT(*) FROM analytics.fact_offer GROUP BY source_id;"

# Check for null values
psql -h localhost -p 5433 -U datauser -d job_db -c \
  "SELECT * FROM analytics.fact_offer WHERE offer_title IS NULL;"
```

#### MongoDB Validation
```bash
# Connect to MongoDB
mongosh "mongodb://admin:admin123@localhost:27017/" --authenticationDatabase admin

# Count raw documents per collection
db.adzuna_raw.countDocuments()
db.rekrute_raw.countDocuments()
db.emploi_public_raw.countDocuments()

# Inspect a sample document
db.adzuna_raw.findOne()
```

### Debugging Tips

#### Airflow DAG Issues
```bash
# Test DAG syntax
docker-compose exec airflow airflow dags list

# Check DAG dependencies
docker-compose exec airflow airflow dags show daily_jobs_pipeline

# View task logs
docker-compose exec airflow tail -f /opt/airflow/logs/daily_jobs_pipeline/*/scrape_adzuna/attempt_*/logs.log

# Restart Airflow scheduler
docker-compose restart airflow-scheduler
```

#### Database Connection Issues
```bash
# Test PostgreSQL connection
docker-compose exec postgres psql -U datauser -d job_db -c "SELECT 1"

# Test MongoDB connection
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"

# Check container logs
docker-compose logs postgres
docker-compose logs mongodb
docker-compose logs airflow-webserver
```

#### Scraper Failures
```bash
# Check scraper logs
docker-compose exec airflow tail -f /opt/airflow/logs/adzuna_scraper.log

# Test scraper directly with limited scope
docker-compose exec airflow python -c \
  "import sys; sys.path.insert(0, '/opt/airflow/scrapers'); \
   from adzuna_scraper import main; main(limit=1)"
```

---

## Database Schema

### Fact Table: `analytics.fact_offer`

| Column | Type | Description |
|--------|------|-------------|
| `offer_id` | UUID | Primary key (unique job posting) |
| `source_id` | SMALLINT | FK → `dim_source` |
| `pays_id` | SMALLINT | FK → `dim_pays` |
| `ville_id` | INT | FK → `dim_ville` |
| `societe_id` | INT | FK → `dim_societe` |
| `date_id` | INT | FK → `dim_date` (scrape date) |
| `offer_title` | VARCHAR(300) | Job title |
| `offer_description` | TEXT | Full job description |
| `salary_min` | DECIMAL(12,2) | Minimum salary (currency varies by country) |
| `salary_max` | DECIMAL(12,2) | Maximum salary |
| `contrat_id` | SMALLINT | FK → `dim_contrat` (contract type) |
| `teletravail_id` | SMALLINT | FK → `dim_teletravail` (remote work) |
| `seniorite_id` | SMALLINT | FK → `dim_seniorite` (experience level) |
| `niveau_diplome_id` | SMALLINT | FK → `dim_niveau_diplome` (education level) |
| `langues` | TEXT[] | Array of required languages |
| `missions` | TEXT[] | Array of job responsibilities |
| `competences` | TEXT[] | Array of required skills |
| `date_scrape` | TIMESTAMP | When data was scraped |
| `date_modification` | TIMESTAMP | Last update timestamp |

### Bridge Table: `analytics.bridge_offer_technologie`

| Column | Type | Description |
|--------|------|-------------|
| `offer_id` | UUID | FK → `fact_offer` |
| `tech_id` | INT | FK → `dim_technologie` |

This bridge table supports many-to-many relationships between job offers and required technologies.

### Dimension Tables (9 total)

- `dim_source` — Data source (Adzuna, ReKrute, Emploi-Public)
- `dim_pays` — Country (France, Morocco)
- `dim_ville` — City
- `dim_societe` — Company name
- `dim_contrat` — Contract type (CDI, CDD, Stage, Alternance, Freelance, Intérim)
- `dim_teletravail` — Remote work policy
- `dim_seniorite` — Experience level (Stage, Junior, Intermédiaire, Confirmé, Senior, Expert)
- `dim_niveau_diplome` — Education level (Bac, Bac+2, Bac+3, Bac+5, Doctorat)
- `dim_technologie` — Tech stack (Python, Java, SQL, etc.)
- `dim_date` — Date hierarchy (year/quarter/month/day)

---

## Performance & Optimization

### Indexing Strategy

PostgreSQL indexes are created on:
- **Dimension tables**: Primary keys (auto-indexed) + unique constraints
- **Fact table**: Foreign key columns for JOIN performance
- **Search optimization**: Trigram index on `dim_societe.societe_nom` (LIKE queries)

```sql
CREATE INDEX idx_fact_offer_source ON analytics.fact_offer(source_id);
CREATE INDEX idx_fact_offer_pays ON analytics.fact_offer(pays_id);
CREATE INDEX idx_dim_societe_trgm ON analytics.dim_societe USING gin (societe_nom gin_trgm_ops);
```

### Scraper Optimization

- **Parallel execution**: All 3 scrapers run simultaneously in Airflow
- **Rate limiting**: 1-2 second delays between API/HTTP requests
- **Batch inserts**: MongoDB upserts in batches of 100-500 documents
- **Caching**: Selenium Chromium instance reused across pages

### Query Performance

Example optimized query (retrieve all data jobs in Morocco):

```sql
SELECT 
    f.offer_id, f.offer_title, s.societe_nom,
    f.salary_min, f.salary_max, c.contrat_libelle
FROM analytics.fact_offer f
JOIN analytics.dim_societe s ON f.societe_id = s.societe_id
JOIN analytics.dim_contrat c ON f.contrat_id = c.contrat_id
WHERE f.pays_id = 1  -- Morocco
  AND 'data' = ANY(f.competences)
ORDER BY f.date_scrape DESC
LIMIT 100;
```

---

## Troubleshooting

### Common Issues

#### 1. Adzuna API 403 Forbidden
**Cause**: Invalid API credentials or rate limit exceeded

**Solution**:
- Verify `ADZUNA_APP_ID` and `ADZUNA_API_KEY` in `.env`
- Get credentials from [Adzuna Developer Portal](https://developer.adzuna.com/)
- Increase `DELAY_BETWEEN_REQUESTS` in `scrapers/adzuna_scraper.py`

#### 2. Selenium Chromium not found
**Cause**: `webdriver-manager` failed to download Chrome driver

**Solution**:
```bash
# Manually download and set Chrome path
export CHROMEDRIVER_PATH=/path/to/chromedriver
python scrapers/emploi_public_scraper.py
```

#### 3. MongoDB connection refused
**Cause**: MongoDB container not running or credentials incorrect

**Solution**:
```bash
docker-compose ps                          # Check container status
docker-compose logs mongodb                # View error logs
docker-compose restart mongodb             # Restart service
```

#### 4. PostgreSQL OOM (Out of Memory)
**Cause**: Large UPSERT operation on `fact_offer` table

**Solution**:
```bash
# Increase Docker memory limit in docker-compose.yml:
services:
  postgres:
    deploy:
      resources:
        limits:
          memory: 4G
```

#### 5. DAG not appearing in Airflow UI
**Cause**: DAG file syntax error or not in `/opt/airflow/dags`

**Solution**:
```bash
# Check DAG validation
docker-compose exec airflow python -m py_compile airflow/dags/daily_jobs_pipeline.py

# View DAG parse errors
docker-compose logs airflow-webserver | grep "ERROR"
```

---

## Contributing

### Development Workflow

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes** and test locally:
   ```bash
   docker-compose up -d
   docker-compose exec airflow python -m pytest tests/ -v
   ```

3. **Commit with descriptive messages:**
   ```bash
   git add .
   git commit -m "feat: add salary estimation for senior roles"
   ```

4. **Push and create a Pull Request:**
   ```bash
   git push origin feature/my-feature
   ```

### Code Style

- **Python**: Follow [PEP 8](https://pep8.org/)
- **SQL**: Use lowercase for keywords, UPPERCASE for table/column names
- **Naming**: descriptive_snake_case for functions/variables, PascalCase for classes
- **Documentation**: Docstrings for all public functions (Google style)

### Adding a New Data Source

1. Create a new scraper: `scrapers/newsource_scraper.py`
2. Create a transformer: `transformers/newsource_transformer.py`
3. Add to DAG in `airflow/dags/daily_jobs_pipeline.py`
4. Update MongoDB collection name in `etl/mongo_to_postgres.py`
5. Add source to `dim_source` in `postgres-init/init-schema.sql`
6. Update this README with new source details

---

## Monitoring & Alerting

### Airflow Health Checks

```bash
# Check scheduler status
curl http://localhost:8080/health

# Get DAG status
curl http://localhost:8080/api/v1/dags/daily_jobs_pipeline

# View failed tasks
curl http://localhost:8080/api/v1/dags/daily_jobs_pipeline/dagRuns \
  | jq '.dag_runs[] | select(.state == "failed")'
```

### Database Health Checks

```bash
# PostgreSQL record count by day
SELECT 
    DATE(date_scrape) as scrape_date,
    COUNT(*) as total_offers,
    COUNT(DISTINCT source_id) as sources
FROM analytics.fact_offer
GROUP BY DATE(date_scrape)
ORDER BY scrape_date DESC
LIMIT 30;

# MongoDB insertion rate
db.adzuna_raw.find().limit(1).hint({_id: -1}).explain("executionStats")
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Authors

- **Marouane Ben** — Project Owner & Lead Developer

---

## Support & Feedback

For issues, feature requests, or questions:

- 📧 **Email**: marouane@jobintelligent.ma
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/isMarouaneBen/FindJob/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/isMarouaneBen/FindJob/discussions)

---

## Acknowledgments

- [Apache Airflow](https://airflow.apache.org/) for workflow orchestration
- [Adzuna API](https://developer.adzuna.com/) for French job data
- [ReKrute.com](https://www.rekrute.com/) and [Emploi-Public.ma](https://www.emploi-public.ma/) for Moroccan job data
- [PostgreSQL](https://www.postgresql.org/) community for stable RDBMS
- [MongoDB](https://www.mongodb.com/) for flexible document storage

---

<div align="center">

Made with ❤️ by the FindJob team

[⬆ Back to Top](#findjob--intelligent-job-aggregation-etl-platform)

</div>