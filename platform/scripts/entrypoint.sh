#!/bin/bash
# Script to run the embedding generation from the container

set -e

echo "🚀 Starting embedding generation..."
echo "Database: $DATABASE_URL"
echo "Model: $EMBEDDING_MODEL"
echo "Device: $DEVICE"

python -u /app/scripts/embed_offers.py

echo "✅ Embedding generation completed!"
