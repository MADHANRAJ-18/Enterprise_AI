"""
backend/processing/embedder.py
─────────────────────────────────────────────────────────────
Stage 4: Embedding generation using local Open-Source / HuggingFace models.

Default Model: sentence-transformers/all-MiniLM-L6-v2 (384-dimensional vectors)

Zero Google Gemini API dependency.
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import os
import time
import logging
import numpy as np
from typing import List, Literal, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM     = int(os.getenv("EMBEDDING_DIMENSION", "384"))
EMBED_BATCH_SIZE  = 32

EmbeddingTaskType = Literal["retrieval_document", "retrieval_query", "semantic_similarity"]


# ── Local Embedding Engine ───────────────────────────────────

class LocalEmbeddingEngine:
    """
    Singleton embedding engine backed by local SentenceTransformer or FastEmbed models.
    Replaces Gemini embeddings with zero cloud API dependencies.
    """

    def __init__(self) -> None:
        self._model_name = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL)
        self._model = None
        self._dim = int(os.getenv("EMBEDDING_DIMENSION", str(EMBEDDING_DIM)))
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            if hasattr(self._model, "get_embedding_dimension"):
                self._dim = self._model.get_embedding_dimension()
            else:
                self._dim = self._model.get_sentence_embedding_dimension()
            logger.info("LocalEmbeddingEngine initialised (SentenceTransformer): model=%s, dim=%d", self._model_name, self._dim)
        except ImportError:
            try:
                from fastembed import TextEmbedding
                self._fast_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
                self._dim = 384
                logger.info("LocalEmbeddingEngine initialised (FastEmbed): model=BAAI/bge-small-en-v1.5, dim=%d", self._dim)
            except ImportError:
                logger.warning(
                    "Neither sentence-transformers nor fastembed is installed. "
                    "Run 'pip install sentence-transformers' for full vector embeddings. "
                    "Using lightweight hash embedding fallback."
                )

    # ── Public API ────────────────────────────────────────────

    def embed_texts(
        self,
        texts: List[str],
        task_type: EmbeddingTaskType = "retrieval_document",
        title: Optional[str] = None,
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        """
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)

        if self._model is not None:
            embeddings = self._model.encode(texts, batch_size=EMBED_BATCH_SIZE, show_progress_bar=False)
            return np.array(embeddings, dtype=np.float32)

        if hasattr(self, "_fast_model") and self._fast_model is not None:
            embeddings_generator = self._fast_model.embed(texts)
            embeddings = list(embeddings_generator)
            return np.array(embeddings, dtype=np.float32)

        # Fallback hash embeddings (guarantees process safety if library missing)
        return self._hash_embeddings(texts)

    def embed_query(self, query: str) -> np.ndarray:
        """Convenience method for embedding a single search query."""
        return self.embed_texts([query], task_type="retrieval_query")[0]

    @property
    def dimension(self) -> int:
        return self._dim

    def _hash_embeddings(self, texts: List[str]) -> np.ndarray:
        """Lightweight deterministic feature hash embeddings when zero ML libs installed."""
        vectors = []
        for text in texts:
            vec = np.zeros(self._dim, dtype=np.float32)
            words = text.lower().split()
            for word in words:
                idx = abs(hash(word)) % self._dim
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)


# Compatibility Aliases
GeminiEmbeddingEngine = LocalEmbeddingEngine

# ── Singleton accessor ────────────────────────────────────────

_engine_instance: Optional[LocalEmbeddingEngine] = None


def get_embedder() -> LocalEmbeddingEngine:
    """Returns the singleton LocalEmbeddingEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LocalEmbeddingEngine()
    return _engine_instance


def reset_embedder() -> None:
    """Reset the singleton (useful for testing)."""
    global _engine_instance
    _engine_instance = None
