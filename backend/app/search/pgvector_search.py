"""pgvector semantic search: generate query embedding + cosine similarity.

Uses FastEmbed (bge-small-en-v1.5) for query-time embedding. Model is
loaded once and cached via lru_cache.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_embedding_model():
    """Lazily load and cache the FastEmbed model.

    The fastembed library is imported here rather than at module top level
    so that merely importing this module (e.g. via app.main) never pays the
    ~1s library import cost in the always-on API process (CLAUDE.md rule 2/5:
    heavy ML deps belong to the batch ingestion path, not the serving path).
    """
    logger.info("Loading embedding model: %s", settings.embedding_model)
    from fastembed import TextEmbedding

    model = TextEmbedding(
        model_name=settings.embedding_model,
        cache_dir=settings.embedding_cache_dir,
    )
    return model


def embed_query(text: str) -> list[float]:
    """Generate a 384-dim embedding for a query string."""
    model = _get_embedding_model()
    embeddings = list(model.embed([text]))
    return embeddings[0]
