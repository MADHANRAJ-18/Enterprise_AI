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

DEFAULT_TOP_K                = int(os.getenv("RAG_TOP_K", "5"))

DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))

MAX_CHUNKS_PER_DOC           = int(os.getenv("RAG_MAX_CHUNKS_PER_DOC", "3"))

CONVERSATIONAL_QUERIES = {

    "hi", "hello", "hey", "heya", "hola", "hi there", "hello there",

    "good morning", "good afternoon", "good evening", "howdy",

    "thanks", "thank you", "bye", "goodbye", "who are you", "what can you do",

    "help", "sup", "yo"

}

@dataclass

class RetrievalResult:
    query:             str

    chunks:            List[SearchResult]

    total_found:       int

    retrieval_time:    float

    used_fallback:     bool  = False

    embedding_model:   str   = ""

    retrieval_scope:   str   = "company"

    @property

    def has_results(self) -> bool:
        return len(self.chunks) > 0

    def log_summary(self) -> None:
        logger.info(

            "Retrieval: query=%r | scope=%s | found=%d | returned=%d | threshold=%.2f | time=%.3fs",

            self.query[:60],

            self.retrieval_scope,

            self.total_found,

            len(self.chunks),

            DEFAULT_SIMILARITY_THRESHOLD,

            self.retrieval_time,

        )

class RetrieverService:
    def __init__(self) -> None:
        self._embedder     = get_embedder()

        self._vector_store = get_vector_store()

        logger.info(

            "RetrieverService initialised: embedder=%s | index_vectors=%d",

            self._embedder._model_name,

            self._vector_store.get_stats()["total_vectors"],

        )

    async def retrieve(

        self,

        query: str,

        top_k: int = DEFAULT_TOP_K,

        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,

        document_ids: Optional[List[str]] = None,

        scope: str = "company",

        user_id: Optional[str] = None,

        company_id: Optional[str] = None,

    ) -> RetrievalResult:
        if not query or not query.strip():
            raise ValueError("query cannot be empty.")

        start = time.perf_counter()

        normalized_q = query.strip().lower().strip("!?.,")

        if normalized_q in CONVERSATIONAL_QUERIES or len(normalized_q) <= 2:
            logger.info(

                "Retrieval fast path: skipped vector search for conversational query %r",

                query[:30],

            )

            return RetrievalResult(

                query=query.strip(),

                chunks=[],

                total_found=0,

                retrieval_time=round(time.perf_counter() - start, 3),

                used_fallback=False,

                embedding_model=self._embedder._model_name,

                retrieval_scope=scope,

            )

        try:
            query_embedding = await asyncio.get_event_loop().run_in_executor(

                None,

                lambda: self._embedder.embed_query(query.strip()),

            )

        except Exception as exc:
            logger.error("Query embedding failed: %s", exc)

            raise RuntimeError(f"Failed to embed query: {exc}") from exc

        fetch_k = min(top_k * 4, 50)

        try:
            if document_ids:
                raw_results: List[SearchResult] = []

                for doc_id in document_ids:
                    doc_results = await asyncio.get_event_loop().run_in_executor(

                        None,

                        lambda d=doc_id: self._vector_store.search(

                            query_embedding, k=fetch_k, filter_doc_id=d

                        ),

                    )

                    raw_results.extend(doc_results)

                raw_results.sort(key=lambda r: r.score, reverse=True)

                raw_results = raw_results[:fetch_k]

            else:
                detected_ids = self._vector_store.find_document_ids_by_filename(query.strip())

                if detected_ids:
                    document_ids = detected_ids

                    logger.info(

                        "Query mentions document filename — restricting search to doc_ids: %s",

                        detected_ids,

                    )

                    raw_results = []

                    for doc_id in detected_ids:
                        doc_results = await asyncio.get_event_loop().run_in_executor(

                            None,

                            lambda d=doc_id: self._vector_store.search(

                                query_embedding, k=fetch_k, filter_doc_id=d

                            ),

                        )

                        raw_results.extend(doc_results)

                    raw_results.sort(key=lambda r: r.score, reverse=True)

                    raw_results = raw_results[:fetch_k]

                else:
                    raw_results = await asyncio.get_event_loop().run_in_executor(

                        None,

                        lambda: self._vector_store.search_scoped(

                            query_embedding,

                            scope=scope,

                            user_id=user_id,

                            k=fetch_k,

                        ),

                    )

        except Exception as exc:
            logger.error("FAISS search failed: %s", exc)

            raise RuntimeError(f"Vector search failed: {exc}") from exc

        filtered = [r for r in raw_results if r.score >= similarity_threshold]

        total_found = len(filtered)

        if MAX_CHUNKS_PER_DOC > 0 and not document_ids:
            filtered = self._cap_per_document(filtered, MAX_CHUNKS_PER_DOC)

        final_chunks = filtered[:top_k]

        used_fallback = len(final_chunks) == 0

        retrieval_time = round(time.perf_counter() - start, 3)

        result = RetrievalResult(

            query=query.strip(),

            chunks=final_chunks,

            total_found=total_found,

            retrieval_time=retrieval_time,

            used_fallback=used_fallback,

            embedding_model=self._embedder._model_name,

            retrieval_scope=scope,

        )

        result.log_summary()

        return result

    async def health_check(self) -> dict:
        results: dict = {}

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

        try:
            stats = self._vector_store.get_stats()

            results["vector_store"] = {

                "status":    "healthy",

                "vectors":   stats["total_vectors"],

                "documents": stats["total_documents"],

            }

        except Exception as exc:
            results["vector_store"] = {"status": "unhealthy", "error": str(exc)}

        return results

    @staticmethod

    def _cap_per_document(

        chunks: List[SearchResult],

        max_per_doc: int,

    ) -> List[SearchResult]:
        doc_counts: dict[str, int] = {}

        out: List[SearchResult] = []

        for chunk in chunks:
            count = doc_counts.get(chunk.document_id, 0)

            if count < max_per_doc:
                out.append(chunk)

                doc_counts[chunk.document_id] = count + 1

        return out

_retriever_instance: Optional[RetrieverService] = None

def get_retriever_service() -> RetrieverService:
    global _retriever_instance

    if _retriever_instance is None:
        _retriever_instance = RetrieverService()

    return _retriever_instance

def reset_retriever_service() -> None:
    global _retriever_instance

    _retriever_instance = None
