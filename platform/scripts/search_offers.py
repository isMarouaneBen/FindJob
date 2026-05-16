#!/usr/bin/env python3
"""
Similarity search script for job offers using embeddings
Searches for offers similar to a given query using vector embeddings
"""
import asyncio
import json
import logging
import os
import sys

from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OfferSearcher:
    """Searches for similar job offers using embeddings"""
    
    def __init__(
        self,
        database_url: str,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        top_k: int = 5
    ):
        """
        Initialize the searcher
        
        Args:
            database_url: PostgreSQL connection string
            model_name: Name of the sentence-transformers model
            top_k: Number of top results to return
        """
        self.database_url = database_url
        self.model_name = model_name
        self.top_k = top_k
        
        self.engine = None
        self.async_session = None
        self.model = None
    
    async def initialize(self):
        """Initialize database connection and embedding model"""
        logger.info("🔄 Initializing searcher...")
        
        # Create database engine
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            future=True,
            pool_pre_ping=True
        )
        
        # Register event listener to set search_path
        from sqlalchemy import event
        @event.listens_for(self.engine.sync_engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("SET search_path TO analytics, public")
            cursor.close()
        
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Load embedding model
        logger.info(f"📦 Loading model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        logger.info("✓ Model loaded")
    
    async def cleanup(self):
        """Clean up resources"""
        if self.engine:
            await self.engine.dispose()
    
    async def search(self, query: str, top_k: int = None) -> list:
        """
        Search for similar job offers
        
        Args:
            query: Search query text
            top_k: Number of results to return (uses self.top_k if not provided)
            
        Returns:
            List of similar offers with scores
        """
        if top_k is None:
            top_k = self.top_k
        
        logger.info(f"🔍 Searching for: '{query}'")
        
        # Generate embedding for query
        query_embedding = self.model.encode(query, convert_to_numpy=False)
        query_embedding_str = str(query_embedding.tolist())
        
        # Search database using cosine similarity
        async with self.async_session() as session:
            result = await session.execute(
                text(f"""
                    SELECT 
                        offer_id,
                        poste,
                        societe_nom,
                        ville_nom,
                        pays_nom,
                        metier_libelle,
                        salaire_min,
                        salaire_max,
                        devise,
                        (1 - (embedding <=> :query_embedding::vector)) * 100 as similarity_score
                    FROM analytics.fact_offer
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> :query_embedding::vector
                    LIMIT :limit
                """),
                {
                    "query_embedding": query_embedding_str,
                    "limit": top_k
                }
            )
            
            offers = []
            for row in result:
                offers.append({
                    "offer_id": row[0],
                    "title": row[1],
                    "company": row[2],
                    "city": row[3],
                    "country": row[4],
                    "job_family": row[5],
                    "salary_min": row[6],
                    "salary_max": row[7],
                    "currency": row[8],
                    "similarity_score": round(float(row[9]), 2)
                })
            
            return offers
    
    async def run(self, query: str, top_k: int = None):
        """Execute search and display results"""
        try:
            await self.initialize()
            
            results = await self.search(query, top_k)
            
            if not results:
                logger.info("❌ No similar offers found")
                return
            
            logger.info(f"✅ Found {len(results)} similar offers:\n")
            
            # Display results in a formatted table
            for i, offer in enumerate(results, 1):
                print(f"\n{i}. {offer['title']}")
                print(f"   Company: {offer['company']}")
                print(f"   Location: {offer['city']}, {offer['country']}")
                print(f"   Job Family: {offer['job_family']}")
                if offer['salary_min'] and offer['salary_max']:
                    print(f"   Salary: {offer['salary_min']}-{offer['salary_max']} {offer['currency']}")
                print(f"   Similarity: {offer['similarity_score']}%")
            
        except Exception as e:
            logger.error(f"❌ Error during search: {e}", exc_info=True)
            return 1
        finally:
            await self.cleanup()
        
        return 0


async def main():
    """Entry point"""
    if len(sys.argv) < 2:
        logger.error("Usage: python search_offers.py '<search query>' [top_k]")
        logger.error("Example: python search_offers.py 'Python Developer' 10")
        return 1
    
    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://datauser:datapass@postgres:5432/job_db"
    )
    model_name = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    searcher = OfferSearcher(
        database_url=database_url,
        model_name=model_name,
        top_k=top_k
    )
    
    return await searcher.run(query, top_k)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
