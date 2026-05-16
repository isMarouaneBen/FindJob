#!/bin/bash
# Example: Running the embedding generation script

# ============================================
# Method 1: Direct Python (local development)
# ============================================

# 1. Install dependencies
pip install -r platform/requirements.txt

# 2. Set up environment variables (optional, defaults shown)
export DATABASE_URL="postgresql+asyncpg://datauser:datapass@localhost:5433/job_db"
export EMBEDDING_MODEL="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
export BATCH_SIZE="32"
export DEVICE="cpu"  # or "cuda" for GPU

# 3. Run the script
python platform/scripts/embed_offers.py

# ============================================
# Method 2: Docker Container (standalone)
# ============================================

# 1. Build the worker image (from project root)
docker build -f platform/Dockerfile.worker -t job-embedding-worker .

# 2. Run the worker container
docker run --network findjob_job_network \
  -e DATABASE_URL="postgresql+asyncpg://datauser:datapass@postgres:5432/job_db" \
  -e EMBEDDING_MODEL="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" \
  -e BATCH_SIZE="32" \
  -e DEVICE="cpu" \
  job-embedding-worker

# ============================================
# Method 3: Docker Compose (one-time job)
# ============================================

# 1. Uncomment the embedding-worker service in docker-compose.yml

# 2. Run it as a one-time job
docker compose run --rm embedding-worker

# Or with custom environment
docker compose run --rm -e DEVICE=cpu embedding-worker

# ============================================
# Method 4: Docker Compose (background service)
# ============================================

# 1. Uncomment embedding-worker in docker-compose.yml
# 2. Change restart policy to "unless-stopped"
# 3. Start with the whole stack

docker compose up embedding-worker -d

# Monitor logs
docker compose logs -f embedding-worker

# ============================================
# Monitoring Progress
# ============================================

# Watch the logs in real-time
docker compose logs -f embedding-worker

# Check database directly (after embedding completes)
docker exec job_postgres psql -U datauser -d job_db -c \
  "SELECT COUNT(*) as total_offers,
          COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as embedded,
          COUNT(CASE WHEN embedding IS NULL THEN 1 END) as pending
   FROM analytics.fact_offer;"

# Check embedding statistics
docker exec job_postgres psql -U datauser -d job_db -c \
  "SELECT 
     COUNT(*) as total_embedded,
     MIN(offer_id) as first_id,
     MAX(offer_id) as last_id,
     array_length(embedding::text::text[], ',')::integer as embedding_dimension
   FROM analytics.fact_offer 
   WHERE embedding IS NOT NULL 
   LIMIT 1;"

# ============================================
# Example Output
# ============================================

# 2026-05-14 10:30:45,123 - __main__ - INFO - 🔄 Initializing embedder...
# 2026-05-14 10:30:45,456 - __main__ - INFO - 📦 Loading model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
# 2026-05-14 10:31:02,789 - __main__ - INFO - ✓ Model loaded (embedding dimension: 384)
# 2026-05-14 10:31:03,012 - __main__ - INFO - 📖 Fetching offers from analytics.v_offer_recommandation...
# 2026-05-14 10:31:04,234 - __main__ - INFO - 📊 Found 1250 offers without embeddings
# 2026-05-14 10:31:04,456 - __main__ - INFO - 🔄 Processing 1250 offers in batches of 32...
# 2026-05-14 10:31:45,123 - __main__ - INFO - ✓ Processed 32/1250 offers (32 embedded)
# 2026-05-14 10:31:50,789 - __main__ - INFO - ✓ Processed 64/1250 offers (64 embedded)
# ...
# 2026-05-14 10:45:30,456 - __main__ - INFO - ✅ Embedding complete! 1250/1250 offers processed

# ============================================
# Troubleshooting
# ============================================

# Out of memory? Use smaller batch size
export BATCH_SIZE="8"

# GPU not detected? Use CPU and install CPU-only torch
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Database connection error? Check:
# 1. PostgreSQL is running: docker compose logs postgres
# 2. Correct database URL
# 3. Network connectivity: docker network ls

# Still stuck? Run with debug logging
# In scripts/embed_offers.py, change logging level to DEBUG
