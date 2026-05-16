# Embedding Generation Script

This directory contains scripts for the Job Intelligence Platform.

## Scripts

### `embed_offers.py`

Reads job offers from `analytics.v_offer_recommandation` and generates semantic embeddings using sentence-transformers.

**Features:**
- Reads offers without embeddings from the recommendation view
- Generates multilingual embeddings (384-dimensional vectors)
- Stores embeddings in `analytics.fact_offer.embedding` column
- Batch processing for efficiency
- Async database operations
- Comprehensive error handling and progress logging

**Usage (Local):**

```bash
# Install dependencies
pip install sentence-transformers torch numpy

# Run the script
python scripts/embed_offers.py
```

**Environment Variables:**

```bash
DATABASE_URL=postgresql+asyncpg://datauser:datapass@postgres:5432/job_db
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
BATCH_SIZE=32
DEVICE=cpu  # or 'cuda' if using GPU
```

**Usage (Docker Container):**

```bash
# Build the worker image
docker build -f Dockerfile.worker -t job-embedding-worker .

# Run the worker
docker run --network findjob_job_network \
  -e DATABASE_URL=postgresql+asyncpg://datauser:datapass@postgres:5432/job_db \
  -e DEVICE=cpu \
  job-embedding-worker
```

**Usage (Docker Compose Service):**

Add to `docker-compose.yml`:

```yaml
embedding-worker:
  build:
    context: .
    dockerfile: platform/Dockerfile.worker
  container_name: job_embedding_worker
  environment:
    DATABASE_URL: postgresql+asyncpg://datauser:datapass@postgres:5432/job_db
    EMBEDDING_MODEL: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
    BATCH_SIZE: 32
    DEVICE: cpu  # Change to 'cuda' for GPU acceleration
  depends_on:
    postgres:
      condition: service_healthy
  networks:
    - job_network
  restart: "no"  # Don't restart after completion
```

Then run:

```bash
docker compose run embedding-worker
# or
docker compose up embedding-worker
```

**What It Does:**

1. Connects to PostgreSQL database
2. Fetches all offers from `analytics.v_offer_recommandation` where `embedding IS NULL`
3. Combines relevant fields (title, company, skills, location, etc.) into text
4. Encodes text into 384-dimensional vectors using sentence-transformers
5. Updates `analytics.fact_offer.embedding` column with vectors
6. Processes in configurable batches for memory efficiency
7. Logs progress and errors

**Output Example:**

```
2026-05-14 10:30:45,123 - __main__ - INFO - 🔄 Initializing embedder...
2026-05-14 10:30:45,456 - __main__ - INFO - 📦 Loading model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
2026-05-14 10:31:02,789 - __main__ - INFO - ✓ Model loaded (embedding dimension: 384)
2026-05-14 10:31:03,012 - __main__ - INFO - 📖 Fetching offers from analytics.v_offer_recommandation...
2026-05-14 10:31:04,234 - __main__ - INFO - 📊 Found 1250 offers without embeddings
2026-05-14 10:31:04,456 - __main__ - INFO - 🔄 Processing 1250 offers in batches of 32...
2026-05-14 10:31:45,123 - __main__ - INFO - ✓ Processed 32/1250 offers (32 embedded)
2026-05-14 10:32:15,789 - __main__ - INFO - ✓ Processed 64/1250 offers (64 embedded)
...
2026-05-14 10:45:30,456 - __main__ - INFO - ✅ Embedding complete! 1250/1250 offers processed
```

## Next Steps

Once embeddings are generated:

1. **Create search endpoint** - Query offers by semantic similarity
2. **Build recommendation engine** - Suggest offers based on user profile
3. **Add filtering** - Combine embeddings with traditional filters
4. **Create web UI** - Browse and search job offers

## Technical Details

- **Model**: `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, multilingual)
- **Vector Type**: pgvector with cosine distance metric
- **Index Type**: IVFFlat with 100 clusters for fast approximate search
- **Async**: Full async/await support for database operations
- **Batch Size**: Configurable (default 32) to balance memory vs speed
