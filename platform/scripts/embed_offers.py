#!/usr/bin/env python3
"""
Embedding generation script for job offers
Reads offers from analytics.v_offer_recommandation and generates embeddings
using sentence-transformers, then stores them in analytics.fact_offer.embedding
"""
import asyncio
import logging
import os
import sys
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OfferEmbedder:
    """Handles embedding generation and storage for job offers"""
    
    def __init__(
        self,
        database_url: str,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        batch_size: int = 32,
        device: str = "cpu"
    ):
        """
        Initialize the embedder
        
        Args:
            database_url: PostgreSQL connection string
            model_name: Name of the sentence-transformers model to use
            batch_size: Number of offers to process in one batch
            device: Device to run the model on ('cpu' or 'cuda')
        """
        self.database_url = database_url
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        
        self.engine = None
        self.async_session = None
        self.model = None
    
    async def initialize(self):
        """Initialize database connection and embedding model"""
        logger.info("🔄 Initializing embedder...")
        
        # Create database engine
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
            pool_size=10
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
        self.model = SentenceTransformer(self.model_name, device=self.device)
        logger.info(f"✓ Model loaded (embedding dimension: {self.model.get_sentence_embedding_dimension()})")
    
    async def cleanup(self):
        """Clean up resources"""
        if self.engine:
            await self.engine.dispose()
        logger.info("✓ Cleanup completed")
    
    def _prepare_text_for_embedding(self, offer: dict) -> str:
        """
        Prepare offer text for embedding by combining relevant fields
        
        Args:
            offer: Offer dict from v_offer_recommandation
            
        Returns:
            Combined text representation
        """
        parts = []
        
        # Title/position (highest weight via repetition)
        if offer.get("poste"):
            parts.extend([offer["poste"]] * 2)
        
        # Job family and seniority
        if offer.get("metier_libelle"):
            parts.append(offer["metier_libelle"])
        if offer.get("seniorite_libelle"):
            parts.append(offer["seniorite_libelle"])
        
        # Company and location
        if offer.get("societe_nom"):
            parts.append(offer["societe_nom"])
        if offer.get("ville_nom"):
            parts.append(offer["ville_nom"])
        
        # Contract and remote work
        if offer.get("contrat_libelle"):
            parts.append(offer["contrat_libelle"])
        if offer.get("teletravail_libelle"):
            parts.append(offer["teletravail_libelle"])
        
        # Skills and competencies
        if offer.get("competences") and isinstance(offer["competences"], list):
            parts.extend(offer["competences"][:10])  # Limit to top 10
        
        # Languages
        if offer.get("langues") and isinstance(offer["langues"], list):
            parts.extend(offer["langues"][:5])  # Limit to top 5
        
        # Salary info (if available)
        if offer.get("salaire_min") and offer.get("salaire_max"):
            parts.append(f"salary {offer['salaire_min']}-{offer['salaire_max']}")
        
        # Join all parts with space
        text = " ".join(str(p).strip() for p in parts if p)
        
        # Truncate to reasonable length (512 tokens ≈ 2000 chars for transformers)
        return text[:2000] if text else "Job offer"
    
    async def fetch_offers(self) -> list:
        """
        Fetch all offers from v_offer_recommandation that don't have embeddings yet
        
        Returns:
            List of offer dicts
        """
        async with self.async_session() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        offer_id,
                        poste,
                        titre_original,
                        societe_nom,
                        ville_nom,
                        pays_nom,
                        metier_libelle,
                        seniorite_libelle,
                        contrat_libelle,
                        teletravail_libelle,
                        competences,
                        langues,
                        salaire_min,
                        salaire_max,
                        devise
                    FROM analytics.v_offer_recommandation
                    WHERE embedding IS NULL
                    ORDER BY offer_id
                    LIMIT 10000
                """)
            )
            
            offers = []
            for row in result:
                offers.append({
                    "offer_id": row[0],
                    "poste": row[1],
                    "titre_original": row[2],
                    "societe_nom": row[3],
                    "ville_nom": row[4],
                    "pays_nom": row[5],
                    "metier_libelle": row[6],
                    "seniorite_libelle": row[7],
                    "contrat_libelle": row[8],
                    "teletravail_libelle": row[9],
                    "competences": row[10],
                    "langues": row[11],
                    "salaire_min": row[12],
                    "salaire_max": row[13],
                    "devise": row[14]
                })
            
            return offers
    
    async def embed_and_store(self, offers: list) -> int:
        """
        Generate embeddings for offers and store them in database
        
        Args:
            offers: List of offer dicts
            
        Returns:
            Number of offers successfully embedded
        """
        if not offers:
            logger.info("📭 No offers to embed")
            return 0
        
        logger.info(f"🔄 Processing {len(offers)} offers in batches of {self.batch_size}...")
        
        total_embedded = 0
        
        # Process in batches
        for batch_idx in range(0, len(offers), self.batch_size):
            batch = offers[batch_idx:batch_idx + self.batch_size]
            
            try:
                # Prepare texts and generate embeddings
                texts = [self._prepare_text_for_embedding(offer) for offer in batch]
                embeddings = self.model.encode(texts, convert_to_numpy=True)
                
                # Store embeddings in database
                async with self.async_session() as session:
                    for offer, embedding in zip(batch, embeddings):
                        # Convert numpy array to list for pgvector
                        embedding_list = embedding.tolist()
                        
                        await session.execute(
                            text("""
                                UPDATE analytics.fact_offer
                                SET embedding = :embedding_vector::vector
                                WHERE offer_id = :offer_id
                            """),
                            {
                                "embedding_vector": str(embedding_list),
                                "offer_id": offer["offer_id"]
                            }
                        )
                    
                    await session.commit()
                
                total_embedded += len(batch)
                progress = min(batch_idx + self.batch_size, len(offers))
                logger.info(f"✓ Processed {progress}/{len(offers)} offers ({total_embedded} embedded)")
                
            except Exception as e:
                logger.error(f"✗ Error processing batch {batch_idx//self.batch_size + 1}: {e}")
                continue
        
        return total_embedded
    
    async def run(self) -> int:
        """
        Main execution method
        
        Returns:
            Total number of embedded offers
        """
        try:
            await self.initialize()
            
            # Fetch offers without embeddings
            logger.info("📖 Fetching offers from analytics.v_offer_recommandation...")
            offers = await self.fetch_offers()
            
            if not offers:
                logger.info("✓ All offers already have embeddings!")
                return 0
            
            logger.info(f"📊 Found {len(offers)} offers without embeddings")
            
            # Generate embeddings and store
            total = await self.embed_and_store(offers)
            
            logger.info(f"✅ Embedding complete! {total}/{len(offers)} offers processed")
            return total
            
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
            return 0
        finally:
            await self.cleanup()


async def main():
    """Entry point for the script"""
    # Get configuration from environment or defaults
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://datauser:datapass@postgres:5432/job_db"
    )
    model_name = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    batch_size = int(os.getenv("BATCH_SIZE", "32"))
    device = os.getenv("DEVICE", "cpu")
    
    # Create and run embedder
    embedder = OfferEmbedder(
        database_url=database_url,
        model_name=model_name,
        batch_size=batch_size,
        device=device
    )
    
    result = await embedder.run()
    return 0 if result >= 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
