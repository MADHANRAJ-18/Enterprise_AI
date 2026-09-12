from __future__ import annotations

import os

import time

import logging

import numpy as np

from typing import List, Literal, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

EMBEDDING_DIM     = int(os.getenv("EMBEDDING_DIMENSION", "384"))

EMBED_BATCH_SIZE  = 32

EmbeddingTaskType = Literal["retrieval_document", "retrieval_query", "semantic_similarity"]

class LocalEmbeddingEngine:
    def __init__(self) -> None:
        self._model_name = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL)

        self._model = None

        self._dim = int(os.getenv("EMBEDDING_DIMENSION", str(EMBEDDING_DIM)))

        self._init_model()

    def _init_model(self):
        try:
            from fastembed import TextEmbedding

            self._fast_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            self._dim = 384
            logger.info("LocalEmbeddingEngine initialised (FastEmbed ONNX): model=BAAI/bge-small-en-v1.5, dim=%d", self._dim)

        except ImportError:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
                if hasattr(self._model, "get_embedding_dimension"):
                    self._dim = self._model.get_embedding_dimension()
                else:
                    self._dim = self._model.get_sentence_embedding_dimension()

                logger.info("LocalEmbeddingEngine initialised (SentenceTransformer): model=%s, dim=%d", self._model_name, self._dim)

            except ImportError:
                logger.warning(
                    "Neither fastembed nor sentence-transformers is installed. "
                    "Using lightweight hash embedding fallback."
                )

    def embed_texts(

        self,

        texts: List[str],

        task_type: EmbeddingTaskType = "retrieval_document",

        title: Optional[str] = None,

    ) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)

        if self._model is not None:
            embeddings = self._model.encode(texts, batch_size=EMBED_BATCH_SIZE, show_progress_bar=False)

            return np.array(embeddings, dtype=np.float32)

        if hasattr(self, "_fast_model") and self._fast_model is not None:
            embeddings_generator = self._fast_model.embed(texts)

            embeddings = list(embeddings_generator)

            return np.array(embeddings, dtype=np.float32)

        return self._hash_embeddings(texts)

    def embed_query(self, query: str) -> np.ndarray:
        return self.embed_texts([query], task_type="retrieval_query")[0]

    @property

    def dimension(self) -> int:
        return self._dim

    def _hash_embeddings(self, texts: List[str]) -> np.ndarray:
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

GeminiEmbeddingEngine = LocalEmbeddingEngine

_engine_instance: Optional[LocalEmbeddingEngine] = None

def get_embedder() -> LocalEmbeddingEngine:
    global _engine_instance

    if _engine_instance is None:
        _engine_instance = LocalEmbeddingEngine()

    return _engine_instance

def reset_embedder() -> None:
    global _engine_instance

    _engine_instance = None
