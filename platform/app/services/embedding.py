"""
Embedding service.

Wraps a single SentenceTransformer instance shared by all requests. The model
is loaded once at startup. Inference runs in a worker thread to avoid blocking
the event loop.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Sequence

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None


def load_model():
    global _model
    if _model is not None:
        return _model
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model %s on %s",
                settings.EMBEDDING_MODEL, settings.EMBEDDING_DEVICE)
    _model = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE)
    dim = _model.get_sentence_embedding_dimension()
    if dim != settings.EMBEDDING_DIM:
        raise RuntimeError(
            f"Model dimension {dim} != configured EMBEDDING_DIM {settings.EMBEDDING_DIM}"
        )
    return _model


def _encode_sync(texts: Sequence[str]) -> np.ndarray:
    model = load_model()
    return model.encode(
        list(texts),
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


async def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    if not texts:
        return []
    arr = await asyncio.to_thread(_encode_sync, texts)
    return arr.tolist()


async def embed_one(text: str) -> List[float]:
    result = await embed_texts([text])
    return result[0]
