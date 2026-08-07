"""
backend/services/retriever_service.py
─────────────────────────────────────────────────────────────
Module 6 – RAG Retriever Service

The core RAG engine. Fully decoupled from the LLM — swap either
component independently.

Pipeline:
  1. embed_query()  → GeminiEmbeddingEngine (retrieval_query task)
  2. faiss.search() → FAISSVectorStore (cosine similarity)
  3. filter()       → drop chunks below similarity_threshold
  4. rank()         → already ordered by FAISS (highest first)
  5. deduplicate()  → optionally cap chunks per document
  6. build_result() → RetrievalResult with formatted metadata

Compatible with Module 7 (LangGraph):
  • retrieve() is async — works as a LangGraph node directly
  • Returns a RetrievalResult dataclass — LangGraph state can store it
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import time
import logging
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

from processing.embedder import get_embedder
from processing.vector_store import get_vector_store, SearchResult

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
DEFAULT_TOP_K               = int(os.getenv("RAG_TOP_K", "5"))
DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))
MAX_CHUNKS_PER_DOC          = int(os.getenv("RAG_MAX_CHUNKS_PER_DOC", "3"))  # 0 = no cap

CONVERSATIONAL_QUERIES = {
    "hi", "hello", "hey", "heya", "hola", "hi there", "hello there",
    "good morning", "good afternoon", "good evening", "howdy",
    "thanks", "thank you", "bye", "goodbye", "who are you", "what can you do",
    "help", "sup", "yo"
}


# ── Result dataclass ──────────────────────────────────────────

@dataclass
class RetrievalResult:
    """
    Output of the retriever pipeline.

    Used by:
      • api/rag.py      → format into RAGChatResponse
      • services/prompt_builder.py → build the context string
      • Module 7 LangGraph nodes  → stored in graph state
    """
    query:              str
    chunks:             List[SearchResult]   # ranked, filtered, deduplicated
    total_found:        int                  # chunks above threshold before top-k
    retrieval_time:     float                # seconds
    used_fallback:      bool = False         # True if no chunks passed the filter
    embedding_model:    str = ""

    @property
    def has_results(self) -> bool:
        return len(self.chunks) > 0

    def log_summary(self) -> None:
        logger.info(
            "Retrieval: query=%r | found=%d | returned=%d | threshold=%.2f | time=%.3fs",
            self.query[:60],
            self.total_found,
            len(self.chunks),
            DEFAULT_SIMILARITY_THRESHOLD,
            self.retrieval_time,
        )


# ── Retriever Service ─────────────────────────────────────────

class RetrieverService:
    """
    End-to-end RAG retrieval pipeline.

    Usage (Module 6 — direct):
        svc = get_retriever_service()
        result = await svc.retrieve("What is the leave policy?")

    Usage (Module 7 — LangGraph node):
        async def retrieval_node(state):
            svc = get_retriever_service()
            result = await svc.retrieve(
                query=state["query"],
                top_k=state.get("top_k", 5),
            )
            return {**state, "retrieval_result": result}
    """

    def __init__(self) -> None:
        self._embedder    = get_embedder()
        self._vector_store = get_vector_store()
        logger.info(
            "RetrieverService initialised: embedder=%s | index_vectors=%d",
            self._embedder._model_name,
            self._vector_store.get_stats()["total_vectors"],
        )

    # ── Public API ────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        document_ids: Optional[List[str]] = None,
    ) -> RetrievalResult:
        """
        Run the full retrieval pipeline for a user query.

        Args:
            query:                 The user's question
            top_k:                 Max chunks to return (after filtering)
            similarity_threshold:  Min cosine similarity to include a chunk
            document_ids:          If set, restrict to these document UUIDs

        Returns:
            RetrievalResult with ranked chunks and metadata
        """
        if not query or not query.strip():
            raise ValueError("query cannot be empty.")

        start = time.perf_counter()

        # ── Fast path: Skip RAG for conversational greetings ─────────
        normalized_q = query.strip().lower().strip("!?.,")
        if normalized_q in CONVERSATIONAL_QUERIES or len(normalized_q) <= 2:
            logger.info("Retrieval fast path: skipped vector search for conversational query %r", query[:30])
            return RetrievalResult(
                query=query.strip(),
                chunks=[],
                total_found=0,
                retrieval_time=round(time.perf_counter() - start, 3),
                used_fallback=False,
                embedding_model=str(self._embedder._model_name),
            )

        # ── Step 1: Embed the query ────────────────────────────
        try:
            query_embedding = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._embedder.embed_query(query.strip()),
            )
        except Exception as exc:
            logger.error("Query embedding failed: %s", exc)
            raise RuntimeError(f"Failed to embed query: {exc}") from exc

        # Auto-detect filename mention in query if explicit document_ids not provided
        is_filename_filtered = False
        target_doc_ids = document_ids
        if not target_doc_ids:
            detected_ids = self._vector_store.find_document_ids_by_filename(query.strip())
            if detected_ids:
                target_doc_ids = detected_ids
                is_filename_filtered = True
                logger.info(
                    "Query explicitly mentions document filename — restricting search to doc_ids: %s",
                    target_doc_ids,
                )

        # ── Step 2: FAISS similarity search ───────────────────
        # Fetch more than top_k to have room for filtering + dedup
        fetch_k = min(top_k * 4, 50)
        try:
            if target_doc_ids:
                # Multi-doc filter: run search for target documents only
                raw_results: List[SearchResult] = []
                for doc_id in target_doc_ids:
                    doc_results = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda d=doc_id: self._vector_store.search(
                            query_embedding, k=fetch_k, filter_doc_id=d
                        ),
                    )
                    raw_results.extend(doc_results)
                # Re-sort by score after merging across target documents
                raw_results.sort(key=lambda r: r.score, reverse=True)
                raw_results = raw_results[:fetch_k]
            else:
                raw_results = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._vector_store.search(query_embedding, k=fetch_k),
                )
        except Exception as exc:
            logger.error("FAISS search failed: %s", exc)
            raise RuntimeError(f"Vector search failed: {exc}") from exc

        # ── Step 3: Filter by similarity threshold ─────────────
        filtered = [r for r in raw_results if r.score >= similarity_threshold]
        total_found = len(filtered)

        # ── Step 4: Per-document deduplication cap ─────────────
        # Only cap per document if search was NOT restricted to specific document(s)
        if MAX_CHUNKS_PER_DOC > 0 and not target_doc_ids:
            filtered = self._cap_per_document(filtered, MAX_CHUNKS_PER_DOC)

        # ── Step 5: Apply top-k ────────────────────────────────
        final_chunks = filtered[:top_k]
        used_fallback = len(final_chunks) == 0

        retrieval_time = round(time.perf_counter() - start, 3)

        result = RetrievalResult(
            query=query.strip(),
            chunks=final_chunks,
            total_found=total_found,
            retrieval_time=retrieval_time,
            used_fallback=used_fallback,
            embedding_model=str(self._embedder._model_name),
        )
        result.log_summary()
        return result

    async def health_check(self) -> dict:
        """Verify the embedder and vector store are operational."""
        results: dict = {}

        # Check embedder
        try:
            start = time.perf_counter()
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._embedder.embed_query("health check"),
            )
            results["embedder"] = {
                "status": "healthy",
                "model": self._embedder._model_name,
                "latency_ms": int((time.perf_counter() - start) * 1000),
            }
        except Exception as exc:
            results["embedder"] = {"status": "unhealthy", "error": str(exc)}

        # Check vector store
        try:
            stats = self._vector_store.get_stats()
            results["vector_store"] = {
                "status": "healthy",
                "vectors": stats["total_vectors"],
                "documents": stats["total_documents"],
            }
        except Exception as exc:
            results["vector_store"] = {"status": "unhealthy", "error": str(exc)}

        return results

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _cap_per_document(
        chunks: List[SearchResult],
        max_per_doc: int,
    ) -> List[SearchResult]:
        """
        Limit the number of chunks from any single document.
        Preserves the existing score ordering (highest first).
        """
        doc_counts: dict[str, int] = {}
        out: List[SearchResult] = []
        for chunk in chunks:
            count = doc_counts.get(chunk.document_id, 0)
            if count < max_per_doc:
                out.append(chunk)
                doc_counts[chunk.document_id] = count + 1
        return out


# ── Singleton accessor ────────────────────────────────────────

_retriever_instance: Optional[RetrieverService] = None


def get_retriever_service() -> RetrieverService:
    """Return the singleton RetrieverService (lazy-initialised)."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RetrieverService()
    return _retriever_instance


def reset_retriever_service() -> None:
    """Reset singleton — useful for testing."""
    global _retriever_instance
    _retriever_instance = None
