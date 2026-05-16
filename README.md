# FindJob — Job Recommendation Engine & Aggregation Platform

<div align="center">

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-00A651.svg)](https://fastapi.tiangolo.com/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-3.8-blue.svg)](https://www.docker.com/)
[![pgvector](https://img.shields.io/badge/pgvector-0.2.5-336791.svg)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-5.0-DC382D.svg)](https://redis.io/)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-Latest-000000.svg)](https://kafka.apache.org/)

**An intelligent job recommendation platform that matches candidates with opportunities using semantic search, hybrid scoring, and CV analysis. Aggregates and enriches job listings from multiple sources across France and Morocco.**

[Overview](#overview) • [Features](#features) • [Architecture](#architecture) • [Quick Start](#quick-start) • [Configuration](#configuration) • [Development](#development)

</div>

---

## Overview

**FindJob** is a comprehensive job intelligence platform consisting of:

### 🎯 Core Platform (FastAPI Recommendation Engine)
- **Semantic job matching** using sentence embeddings (multilingual MiniLM)
- **Hybrid scoring** combining vector similarity, skill overlap, seniority, contract type, location, and remote policy
- **CV upload & parsing** with automatic profile extraction from PDF/DOCX/TXT files
- **Real-time recommendations** matching candidates against the job database
- **Smart caching** with Redis for performance optimization
- **Async processing** using Kafka for CV parsing and embedding generation

### 📊 Supporting Infrastructure (ETL Pipeline)
- **Multi-source aggregation** from Adzuna (France), ReKrute (Morocco), Emploi-Public.ma (Morocco)
- **Data transformation** with salary estimation, skill extraction, and geolocation normalization
- **Analytics data warehouse** with star schema for BI and reporting
- **Daily orchestration** via Apache Airflow

The platform implements a **medallion architecture** (Bronze → Silver → Gold) with:
- **MongoDB** as Bronze layer (raw ingestion)
- **PostgreSQL** with pgvector as Silver/Gold layers (transformed, analytics-ready data with embeddings)

Perfect for job marketplaces, talent platforms, and recruitment analytics.

---

## Features

### 🤖 Recommendation Engine
- **Semantic search** with pgvector (384-dim multilingual embeddings)
- **Hybrid scoring** algorithm weighting: vector (55%) + tech overlap (20%) + seniority (8%) + contract (5%) + location (5%) + remote (4%) + language (3%)
- **CV upload & parsing** supporting PDF, DOCX, TXT formats (max 5MB)
- **Async CV processing** via Kafka worker with Redis caching
- **Real-time API** built on FastAPI with async/await
- **Top-K retrieval** with configurable candidate pool size (200 pre-filtered by ANN, re-ranked for top-20)

### 📤 Job Ingestion & Enrichment
- **Multi-source scraping**: Adzuna API (France), ReKrute (Morocco), Emploi-Public.ma (Morocco)
- **Parallel extraction**: 3 independent scrapers running concurrently
- **ML-based salary estimation**: Predicts salary ranges for jobs with missing data
- **NLP skill extraction**: Automatic technology & requirement detection
- **Geolocation normalization**: Standardized city/country across sources
- **Multi-language support**: French, Arabic, and English text processing

### 💾 Data Architecture
- **Star schema**: 1 fact table + 10 dimension tables (Kimball methodology)
- **Vector embeddings**: Semantic job embeddings stored in pgvector column
- **Efficient indexing**: IVFFlat index on embeddings for fast ANN queries
- **Bridge tables**: Many-to-many relationships for technologies and skills
- **Audit trails**: Timestamps for scraping, parsing, and modification

### ⚙️ Infrastructure & Reliability
- **Async worker pool**: Kafka-based consumer for background CV parsing
- **Redis caching**: Recommendation results cached for 5 minutes
- **MinIO storage**: Scalable object storage for uploaded CVs
- **Database connection pooling**: 10 base + 20 overflow connections
- **Fault tolerance**: Automatic retries with configurable backoff
- **Structured logging**: JSON logs for all pipeline stages

---

## Architecture

### System Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                    │
│  ┌──────────────┐          ┌──────────────┐                        │
│  │ Web Frontend │          │   Mobile App │                        │
│  └──────────────┘          └──────────────┘                        │
└────────┬──────────────────────────────────┬────────────────────────┘
         │                                  │
         │         POST /api/v1/           │
         └─────────────┬────────────────────┘
                       ▼
      ┌────────────────────────────────────────┐
      │    FASTAPI RECOMMENDATION ENGINE       │
      │  ┌──────────────────────────────────┐  │
      │  │ GET  /health                     │  │
      │  │ POST /cv/upload                  │  │
      │  │ POST /recommendations            │  │
      │  │ POST /recommendations/from-cv    │  │
      │  │ GET  /offers                     │  │
      │  │ POST /profiles                   │  │
      │  └──────────────────────────────────┘  │
      │         (Hybrid Scoring)               │
      └────────────┬──────────────┬─────────────┘
                   │              │
         ┌─────────┴──────┐       │
         ▼                ▼       │
    ┌─────────┐      ┌─────────┐ │
    │  Redis  │      │ MinIO   │ │
    │ (Cache) │      │ (CVs)   │ │
    └─────────┘      └─────────┘ │
                                 ▼
                    ┌────────────────────────┐
                    │  PostgreSQL + pgvector │
                    │ ┌────────────────────┐ │
                    │ │ fact_offer         │ │
                    │ │  └─ embedding vec │ │
                    │ │  └─ tech_ids[]    │ │
                    │ └────────────────────┘ │
                    │ DIMENSIONS:            │
                    │ • dim_source           │
                    │ • dim_pays/ville       │
                    │ • dim_societe          │
                    │ • dim_contrat          │
                    │ • dim_technologie      │
                    └────────────────────────┘
                                 ▲
         ┌───────────────────────┴───────────────────────┐
         │                                               │
         ▼                                               ▼
    ┌─────────────┐                           ┌──────────────────┐
    │   KAFKA     │                           │ AIRFLOW ETL      │
    │ cv.uploaded │                           │ (6am daily)      │
    │  (worker)   │                           │                  │
    └─────────────┘                           └──────────────────┘
         │                                           │
         ▼                                           ▼
    ┌─────────────────┐              ┌────────────────────────────┐
    │ CV Parser       │              │ MONGODB (BRONZE)           │
    │ • Extract text  │              │ • adzuna_raw               │
    │ • Generate emb. │              │ • rekrute_raw              │
    │ • Store profile │              │ • emploi_public_raw        │
    └─────────────────┘              └────────────────────────────┘
         ▼                                           │
    ┌─────────────────┐                           ▼
    │ Redis cache:    │              ┌────────────────────────────┐
    │ cv:profile:{id} │              │ TRANSFORMERS (SILVER)      │
    │ cv:embedding{id}│              │ • adzuna_transformer       │
    └─────────────────┘              │ • rekrute_transformer      │
                                     │ • salary_estimator        │
                                     └────────────────────────────┘
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
- **~6 GB** free disk space (includes embedding model + data)
- **Windows/Mac/Linux** with WSL2 (on Windows)

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/isMarouaneBen/findjob.git
   cd findjob
   ```

2. **Create environment file (`.env`):**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with required values:
   ```env
   # API Keys (get from Adzuna Developer Portal)
   ADZUNA_APP_ID=your_app_id
   ADZUNA_API_KEY=your_api_key

   # Airflow credentials
   AIRFLOW_ADMIN_USER=admin
   AIRFLOW_ADMIN_PASSWORD=admin123
   AIRFLOW_ADMIN_EMAIL=admin@example.com

   # Default values for FastAPI service (override if needed)
   # DATABASE_URL=postgresql+asyncpg://datauser:datapass@postgres:5432/job_db
   # REDIS_URL=redis://redis:6379/0
   # KAFKA_BOOTSTRAP_SERVERS=kafka:9092
   ```

3. **Start the full stack:**
   ```bash
   docker-compose up -d
   ```

4. **Initialize Airflow (first time only):**
   ```bash
   docker-compose exec airflow airflow db init
   docker-compose exec airflow airflow users create \
     --role Admin \
     --username admin \
     --email admin@example.com \
     --firstname Admin \
     --lastname User \
     --password admin123
   ```

5. **Access the services:**
   - **FastAPI API** (Recommendation Engine): http://localhost:8000
   - **FastAPI Docs**: http://localhost:8000/docs
   - **Airflow WebUI**: http://localhost:8080 (admin/admin123)
   - **pgAdmin**: http://localhost:5050 (admin@example.com/admin123)
   - **PostgreSQL**: localhost:5432 (datauser:datapass)
   - **MongoDB**: localhost:27017 (admin:admin123)
   - **Redis**: localhost:6379 (no password)

### Quick API Test

**1. Upload a CV:**
```bash
curl -X POST http://localhost:8000/api/v1/cv/upload \
  -F "file=@cv_test/english_resume.pdf"
```
Response:
```json
{
  "cv_id": "db0ff853df354ef89d90dff04db0edc3",
  "object_key": "db0ff853df354ef89d90dff04db0edc3.pdf",
  "bucket": "cv-uploads",
  "status": "queued",
  "message": "CV uploaded; parsing scheduled."
}
```

**2. Get recommendations based on CV (wait 2-5 seconds for async parsing):**
```bash
curl -X POST http://localhost:8000/api/v1/recommendations/from-cv \
  -H "Content-Type: application/json" \
  -d '{"cv_id": "db0ff853df354ef89d90dff04db0edc3", "top_k": 20}'
```

**3. Get recommendations from profile data (synchronous):**
```bash
curl -X POST http://localhost:8000/api/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Data Engineer",
    "description": "Passionate about building scalable data pipelines with Python, Apache Spark, and PostgreSQL",
    "skills": ["Python", "Apache Spark", "PostgreSQL", "Kafka"],
    "seniority_level": "mid",
    "preferred_contract": "CDI",
    "preferred_location": "Paris",
    "remote_preference": "flexible",
    "languages": ["French", "English"],
    "top_k": 20
  }'
```

**4. Browse available job offers:**
```bash
curl "http://localhost:8000/api/v1/offers?skip=0&limit=10&source=adzuna"
```

**5. Check API health:**
```bash
curl http://localhost:8000/api/v1/health
```

### Trigger ETL Pipeline

**Option 1: Manual trigger via Airflow CLI**
```bash
docker-compose exec airflow airflow dags trigger daily_jobs_pipeline
```

**Option 2: Via Airflow WebUI**
1. Navigate to http://localhost:8080
2. Find `daily_jobs_pipeline` DAG
3. Click "Trigger DAG"

---

## Configuration

### FastAPI Application Settings

[platform/app/core/config.py](platform/app/core/config.py) manages all settings:

| Variable | Description | Default |
|----------|-------------|----------|
| `EMBEDDING_MODEL` | Sentence transformer model | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `EMBEDDING_DIM` | Embedding vector dimension | `384` |
| `EMBEDDING_DEVICE` | Inference device (cpu/cuda) | `cpu` |
| `REDIS_CACHE_TTL_SECONDS` | Recommendation cache lifetime | `300` |
| `RECO_DEFAULT_TOP_K` | Default recommendation count | `20` |
| `RECO_VECTOR_CANDIDATES` | ANN candidate pool size | `200` |
| `RECO_WEIGHT_*` | Hybrid scoring weights | See [config.py](platform/app/core/config.py) |
| `MINIO_BUCKET_CV` | CV storage bucket | `cv-uploads` |
| `KAFKA_TOPIC_CV_UPLOADED` | Async processing topic | `cv.uploaded` |

### Recommendation Scoring Algorithm

The hybrid recommendation engine combines six signals:

$$
\text{Score} = 0.55 \times \text{VectorSimilarity} + 0.20 \times \text{TechOverlap} + 0.08 \times \text{SeniorityMatch}
+ 0.05 \times \text{ContractMatch} + 0.05 \times \text{LocationMatch} + 0.04 \times \text{RemoteMatch} + 0.03 \times \text{LanguageMatch}
$$

**Components:**
- **Vector Similarity** (55%): Cosine distance in embedding space (semantic relevance)
- **Tech Overlap** (20%): Jaccard similarity of skill sets
- **Seniority Match** (8%): How well job seniority aligns with candidate level
- **Contract Type** (5%): Job contract preference matching
- **Location** (5%): Geographic preference matching
- **Remote Policy** (4%): Work location preference (office/hybrid/remote)
- **Language** (3%): Required language proficiency matching

---

## API Endpoints

### Health & Status

**GET /api/v1/health**

Check API and dependencies health.

### CV Upload & Profile Extraction

**POST /api/v1/cv/upload**

Upload a CV file (PDF, DOCX, or TXT) for parsing and recommendations.
- **Accepted formats**: `.pdf`, `.docx`, `.txt`
- **Max size**: 5 MB
- **Returns**: CV ID for use with recommendation endpoints
- **Async processing**: CV is parsed asynchronously by a Kafka worker

### Recommendations

**POST /api/v1/recommendations**

Get job recommendations from a profile payload (synchronous).

**POST /api/v1/recommendations/from-cv**

Get job recommendations based on a previously uploaded CV.

### Job Offers

**GET /api/v1/offers**

Browse and search job offers with filtering options.

Query parameters:
- `skip` (int): Pagination offset (default: 0)
- `limit` (int): Results per page (default: 10, max: 100)
- `source` (str): Filter by source (adzuna, rekrute, emploi_public)
- `country` (str): Filter by country (fr, ma)
- `city` (str): Filter by city name
- `salary_min` (float): Minimum salary filter
- `salary_max` (float): Maximum salary filter
- `contract_type` (str): Filter by contract (CDI, CDD, Stage, etc.)
- `remote` (str): Filter by remote policy (onsite, hybrid, remote)

### Profiles

**POST /api/v1/profiles**

Parse and extract profile from form data (synchronous). Alternative to CV upload.

See [API Documentation](http://localhost:8000/docs) for complete endpoint specifications and request/response schemas.

---

## Airflow ETL Configuration

### DAG Schedule & Settings

Key settings in [airflow/dags/daily_jobs_pipeline.py](airflow/dags/daily_jobs_pipeline.py):

```python
schedule_interval="0 6 * * *",      # Daily at 06:00 UTC
max_active_runs=1,                   # Prevent concurrent runs
retries=2,                           # Retry failed tasks 2x
retry_delay=timedelta(minutes=5),    # Wait 5 min between retries
```

### Scraper Configuration

#### Adzuna Scraper
Searches for data roles in France via the Adzuna API:
- **Keywords**: Data scientist, engineer, analyst, machine learning
- **Country**: France
- **Rate Limit**: 1 second delay between requests
- **Max Results**: 1000 per run (20 pages × 50 results)

#### ReKrute Scraper
Web scrapes job listings from ReKrute.com (Morocco)
- **Base URL**: `https://www.rekrute.com`
- **Pagination**: 50 results per page

#### Emploi-Public Scraper
Automates scraping from Emploi-Public.ma (Morocco) using Selenium
- **Browser**: Headless Chrome automation
- **PDF Parsing**: Extracts text from PDF job descriptions

### Transformers (Silver Layer)

Data normalization and enrichment:
- **Salary Estimation**: ML-based prediction for missing salary data
- **Skill Extraction**: Automatic technology detection and categorization
- **Geolocation**: Standardized city and country names
- **Schema Unification**: Converts source-specific formats to common schema

---

## Development

### Project Structure

```
findjob/
├── platform/                         # FastAPI Application (Main)
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint
│   │   ├── api/v1/
│   │   │   ├── cv.py                # CV upload endpoint
│   │   │   ├── recommendations.py   # Recommendation endpoints
│   │   │   ├── offers.py            # Browse job offers
│   │   │   ├── profiles.py          # Profile parsing
│   │   │   ├── health.py            # Health check
│   │   │   └── router.py            # API router
│   │   ├── core/
│   │   │   ├── config.py            # Settings management
│   │   │   └── logging.py           # Structured logging
│   │   ├── db/session.py            # SQLAlchemy setup
│   │   ├── schemas/                 # Pydantic models
│   │   ├── services/                # Business logic
│   │   │   ├── matching.py          # Hybrid recommendation
│   │   │   ├── embedding.py         # Embedding generation
│   │   │   ├── cv_parser.py         # CV parsing
│   │   │   ├── redis_client.py      # Redis cache
│   │   │   ├── minio_client.py      # MinIO storage
│   │   │   ├── kafka_producer.py    # Event publishing
│   │   │   ├── tech_extractor.py    # Skill extraction
│   │   │   └── tech_vocab.py        # Technology vocabulary
│   │   ├── workers/
│   │   │   └── cv_consumer.py       # Kafka consumer for CV processing
│   │   └── repositories/            # Database queries
│   ├── requirements.txt             # Python dependencies
│   ├── Dockerfile                   # Container image
│   └── Dockerfile.worker            # Worker process image
│
├── airflow/                         # Orchestration
│   ├── dags/
│   │   └── daily_jobs_pipeline.py   # Main ETL DAG
│   ├── logs/                        # Execution logs
│   ├── plugins/                     # Custom operators
│   ├── requirements.txt
│   └── Dockerfile
│
├── scrapers/                        # Bronze Layer (Data Ingestion)
│   ├── adzuna_scraper.py            # France jobs
│   ├── rekrute_scraper.py           # Morocco jobs
│   ├── emploi_public_scraper.py     # Morocco public sector
│   └── requirements.txt
│
├── transformers/                    # Silver Layer (Data Transformation)
│   ├── adzuna_transformer.py
│   ├── rekrute_transformer.py
│   ├── emploi_public_transformer.py
│   ├── salary_estimator.py          # ML salary prediction
│   ├── skill_normalizer.py          # Technology extraction
│   ├── geo_normalizer.py            # Location standardization
│   ├── job_family.py                # Role classification
│   └── enrichment.py
│
├── etl/
│   └── mongo_to_postgres.py         # MongoDB → PostgreSQL loader
│
├── data/
│   ├── raw/                         # Sample raw data
│   └── data/                        # Sample transformed data
│
├── db_snapshot/
│   └── data_snapshot.dump           # PostgreSQL backup
│
├── dashboard/
│   ├── power bi dashboard.fig       # BI dashboard
│   └── Revenue and Profitability.json
│
├── postgres-init/                   # PostgreSQL initialization
│   ├── 00-roles.sql
│   ├── 01-schema.sql                # Star schema definition
│   ├── 02-cleanup-and-constraints.sql
│   ├── 03-enrichment.sql
│   └── Dockerfile
│
├── mongo-init/
│   └── 00-roles.sql
│
├── cv_test/                         # Test CVs
│   └── english_resume.pdf
│
├── docker-compose.yml               # Services orchestration
├── .env.example                     # Environment template
├── EMBEDDING_USAGE.md               # Embedding deployment guide
├── README.md                        # This file
└── pass.txt                         # Credentials reference
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