"""
backend/processing/vector_store.py
─────────────────────────────────────────────────────────────
Stage 5: FAISS vector index management.

Design:
  • Uses FAISS IndexFlatIP (inner product / cosine similarity)
    with 768-dimensional vectors (Gemini text-embedding-004)
  • Singleton pattern — one index per process
  • Persisted to disk: faiss_index/index.faiss + faiss_index/metadata.json
  • Tracks doc_id → list of vector IDs for targeted deletion
  • Provides search interface for Module 5 RAG retriever

Index storage layout:
  backend/
  └── faiss_index/
      ├── index.faiss      ← FAISS binary index file
      └── metadata.json    ← doc_id → [vector_ids] + chunk text mapping

Note on cosine similarity:
  Gemini embeddings are NOT unit-normalised by default.
  We L2-normalise before adding to IndexFlatIP so that inner
  product == cosine similarity.
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import os
import json
import logging
import threading
import numpy as np
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────
EMBEDDING_DIM    = int(os.getenv("EMBEDDING_DIMENSION", "384"))
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_index")
FAISS_INDEX_FILE = os.path.join(FAISS_INDEX_PATH, "index.faiss")
FAISS_META_FILE  = os.path.join(FAISS_INDEX_PATH, "metadata.json")


# ── Data structures ───────────────────────────────────────────

@dataclass
class SearchResult:
    """A single result from a FAISS similarity search."""
    vector_id: int              # FAISS internal vector ID
    score: float                # Cosine similarity (0–1, higher = more similar)
    document_id: str            # Supabase document UUID
    chunk_index: int            # 0-based chunk position
    chunk_text: str             # The raw chunk text
    file_name: str              # Original filename
    category: str               # Document category
    page_number: Optional[int]  # Page number if available


# ── FAISS Vector Store ────────────────────────────────────────

class FAISSVectorStore:
    """
    Thread-safe FAISS index manager with document-level metadata tracking.

    Persists to disk automatically after every mutation (add / remove).
    The index can be loaded at server startup via load().
    """

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim
        self._lock = threading.Lock()

        # FAISS index (IndexFlatIP for cosine similarity after L2 norm)
        self._index = self._create_index()

        # Metadata sidecar: maps vector_id (int) → chunk metadata dict
        # Also tracks doc_id → list[vector_id] for deletion
        self._meta: Dict[str, Any] = {
            "vectors": {},    # str(vector_id) → {doc_id, chunk_index, chunk_text, ...}
            "doc_ids": {},    # doc_id → [vector_ids]
        }

        # Next available vector ID (FAISS uses sequential integer IDs)
        self._next_id: int = 0

        # Load existing index from disk if available
        self._load_if_exists()

    # ── Public: Indexing ──────────────────────────────────────

    def add_chunks(
        self,
        document_id: str,
        embeddings: np.ndarray,
        chunk_metadata: List[Dict[str, Any]],
    ) -> List[int]:
        """
        Add document chunk embeddings to the FAISS index.

        Args:
            document_id:    Supabase document UUID
            embeddings:     np.ndarray shape (n_chunks, dim)
            chunk_metadata: List of dicts with keys:
                            chunk_index, chunk_text, file_name,
                            category, page_number

        Returns:
            List of assigned vector IDs

        Raises:
            ValueError: if shapes don't match
        """
        if embeddings.shape[0] == 0:
            logger.warning("add_chunks called with 0 embeddings for doc %s", document_id)
            return []

        if embeddings.shape[1] != self._dim:
            raise ValueError(
                f"Embedding dimension mismatch: got {embeddings.shape[1]}, "
                f"expected {self._dim}."
            )

        with self._lock:
            # Remove existing vectors if re-indexing
            if document_id in self._meta["doc_ids"]:
                logger.info("Re-indexing doc %s — removing old vectors first", document_id)
                self._remove_document_unsafe(document_id)

            # L2-normalise for cosine similarity via inner product
            normed = self._l2_normalize(embeddings)

            # Assign sequential vector IDs
            n = embeddings.shape[0]
            vector_ids = list(range(self._next_id, self._next_id + n))
            self._next_id += n

            # Add to FAISS with explicit IDs
            ids_array = np.array(vector_ids, dtype=np.int64)
            self._index.add_with_ids(normed, ids_array)

            # Store metadata
            for vid, meta in zip(vector_ids, chunk_metadata):
                self._meta["vectors"][str(vid)] = {
                    "document_id": document_id,
                    "chunk_index": meta.get("chunk_index", 0),
                    "chunk_text": meta.get("chunk_text", ""),
                    "file_name": meta.get("file_name", ""),
                    "category": meta.get("category", ""),
                    "page_number": meta.get("page_number"),
                }

            # Track doc_id → vector_ids mapping
            self._meta["doc_ids"][document_id] = vector_ids

            self._persist()

        logger.info(
            "Indexed %d chunks for doc %s (total vectors: %d)",
            n, document_id, self._index.ntotal,
        )
        return vector_ids

    # ── Public: Search ────────────────────────────────────────

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        filter_doc_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Search for the k most similar chunks to a query embedding.

        Args:
            query_embedding: 1-D or 2-D np.ndarray of shape (dim,) or (1, dim)
            k:               Number of results to return
            filter_doc_id:   If provided, only return chunks from this document

        Returns:
            List of SearchResult ordered by similarity (highest first)
        """
        if self._index.ntotal == 0:
            return []

        # Ensure 2D shape (1, dim)
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        # L2-normalise the query too
        normed_query = self._l2_normalize(query_embedding.astype(np.float32))

        with self._lock:
            # Fetch extra results if filtering (to ensure k after filter)
            fetch_k = min(k * 3 if filter_doc_id else k, self._index.ntotal)
            scores, ids = self._index.search(normed_query, fetch_k)

        results: List[SearchResult] = []
        for score, vid in zip(scores[0], ids[0]):
            if vid == -1:  # FAISS returns -1 for empty slots
                continue

            meta = self._meta["vectors"].get(str(vid))
            if not meta:
                continue

            if filter_doc_id and meta["document_id"] != filter_doc_id:
                continue

            results.append(SearchResult(
                vector_id=int(vid),
                score=float(score),
                document_id=meta["document_id"],
                chunk_index=meta["chunk_index"],
                chunk_text=meta["chunk_text"],
                file_name=meta.get("file_name", ""),
                category=meta.get("category", ""),
                page_number=meta.get("page_number"),
            ))

            if len(results) >= k:
                break

        return results

    # ── Public: Deletion ──────────────────────────────────────

    def remove_document(self, document_id: str) -> int:
        """
        Remove all vectors for a document from the index.
        Returns the number of vectors removed.
        """
        with self._lock:
            n = self._remove_document_unsafe(document_id)
            if n > 0:
                self._persist()
        logger.info("Removed %d vectors for doc %s", n, document_id)
        return n

    def _remove_document_unsafe(self, document_id: str) -> int:
        """Remove vectors without acquiring the lock (caller holds it)."""
        vector_ids = self._meta["doc_ids"].get(document_id, [])
        if not vector_ids:
            return 0

        ids_to_remove = np.array(vector_ids, dtype=np.int64)
        self._index.remove_ids(ids_to_remove)

        for vid in vector_ids:
            self._meta["vectors"].pop(str(vid), None)
        del self._meta["doc_ids"][document_id]

        return len(vector_ids)

    # ── Public: Stats ─────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Returns index statistics."""
        return {
            "total_vectors": self._index.ntotal,
            "total_documents": len(self._meta["doc_ids"]),
            "dimension": self._dim,
            "index_path": FAISS_INDEX_FILE,
        }

    def document_is_indexed(self, document_id: str) -> bool:
        """Returns True if the document already has vectors in the index."""
        return document_id in self._meta["doc_ids"]

    def find_document_ids_by_filename(self, query: str) -> List[str]:
        """
        Detect if the user query explicitly mentions any indexed document filename
        (or base filename without extension, with or without underscores/dashes).
        Returns matching list of document_ids.
        """
        if not query or not self._meta.get("vectors"):
            return []

        query_lower = query.lower()
        matched_doc_ids = set()

        # Build doc_id -> filename mapping from vectors metadata
        doc_filenames: Dict[str, str] = {}
        for meta in self._meta["vectors"].values():
            doc_id = meta.get("document_id")
            fname = meta.get("file_name")
            if doc_id and fname:
                doc_filenames[doc_id] = fname

        for doc_id, fname in doc_filenames.items():
            fname_lower = fname.lower()
            base_name = os.path.splitext(fname_lower)[0]

            clean_base = base_name.replace("_", " ").replace("-", " ")
            clean_query = query_lower.replace("_", " ").replace("-", " ")

            if (
                fname_lower in query_lower or
                base_name in query_lower or
                clean_base in clean_query or
                (len(base_name) > 5 and base_name in query_lower.replace(".pdf", "").replace(".docx", "").replace(".txt", ""))
            ):
                matched_doc_ids.add(doc_id)

        return list(matched_doc_ids)

    # ── Internal: Index creation ──────────────────────────────

    def _create_index(self):
        """Create a new FAISS IndexIDMap2 (Inner Product, supports remove)."""
        try:
            import faiss
        except ImportError:
            raise ImportError("faiss-cpu is required. Run: pip install faiss-cpu")

        flat_index = faiss.IndexFlatIP(self._dim)
        # IDMap2 wraps the flat index and supports add_with_ids + remove_ids
        index = faiss.IndexIDMap2(flat_index)
        return index

    # ── Internal: Persistence ─────────────────────────────────

    def _persist(self) -> None:
        """Save the FAISS index and metadata sidecar to disk."""
        try:
            import faiss
            os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
            faiss.write_index(self._index, FAISS_INDEX_FILE)
            with open(FAISS_META_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "next_id": self._next_id,
                    **self._meta,
                }, f, indent=2)
        except Exception as exc:
            logger.error("Failed to persist FAISS index: %s", exc)

    def _load_if_exists(self) -> None:
        """Load an existing FAISS index and metadata from disk."""
        if not os.path.exists(FAISS_INDEX_FILE):
            logger.info("No existing FAISS index found — starting fresh.")
            return

        try:
            import faiss
            self._index = faiss.read_index(FAISS_INDEX_FILE)
            with open(FAISS_META_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._next_id = data.get("next_id", 0)
            self._meta["vectors"] = data.get("vectors", {})
            self._meta["doc_ids"] = data.get("doc_ids", {})

            if getattr(self._index, "d", None) != self._dim:
                logger.warning(
                    "FAISS index dimension mismatch: file index has dim %d, "
                    "configured dimension is %d. Resetting FAISS index.",
                    getattr(self._index, "d", 0), self._dim,
                )
                self._index = self._create_index()
                self._meta = {"vectors": {}, "doc_ids": {}}
                self._next_id = 0
                self._persist()
            else:
                logger.info(
                    "FAISS index loaded: %d vectors, %d documents (dim %d)",
                    self._index.ntotal, len(self._meta["doc_ids"]), self._dim,
                )
        except Exception as exc:
            logger.warning("Failed to load FAISS index (%s) — starting fresh.", exc)
            self._index = self._create_index()
            self._meta = {"vectors": {}, "doc_ids": {}}
            self._next_id = 0

    # ── Internal: Math ────────────────────────────────────────

    @staticmethod
    def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
        """L2-normalise rows so inner product == cosine similarity."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-10, norms)  # avoid division by zero
        return (vectors / norms).astype(np.float32)


# ── Singleton accessor ────────────────────────────────────────

_store_instance: Optional[FAISSVectorStore] = None


def get_vector_store() -> FAISSVectorStore:
    """
    Returns the singleton FAISSVectorStore instance.
    Loads existing index from disk on first call.
    """
    global _store_instance
    if _store_instance is None:
        _store_instance = FAISSVectorStore()
    return _store_instance


def reset_vector_store() -> None:
    """Reset singleton (useful for testing)."""
    global _store_instance
    _store_instance = None
