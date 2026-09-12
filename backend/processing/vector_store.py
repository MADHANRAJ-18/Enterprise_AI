from __future__ import annotations

import os

import json

import logging

import threading

import numpy as np

from typing import List, Dict, Optional, Any, cast

from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EMBEDDING_DIM    = int(os.getenv("EMBEDDING_DIMENSION", "384"))

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_index")

FAISS_INDEX_FILE = os.path.join(FAISS_INDEX_PATH, "index.faiss")

FAISS_META_FILE  = os.path.join(FAISS_INDEX_PATH, "metadata.json")

@dataclass

class SearchResult:
    vector_id:   int

    score:       float

    document_id: str

    chunk_index: int

    chunk_text:  str

    file_name:   str

    category:    str

    page_number: Optional[int]

    scope:       str = "company"

    user_id:     Optional[str] = None

    @property

    def chunk_id(self) -> str:
        return f"{self.document_id}::chunk_{self.chunk_index}"

class FAISSVectorStore:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim

        self._lock = threading.Lock()

        self._index = self._create_index()

        self._meta: Dict[str, Any] = {

            "vectors": {},

            "doc_ids": {},

        }

        self._next_id: int = 0

        self._load_if_exists()

    def add_chunks(

        self,

        document_id: str,

        embeddings: np.ndarray,

        chunk_metadata: List[Dict[str, Any]],

    ) -> List[int]:
        if embeddings.shape[0] == 0:
            logger.warning("add_chunks called with 0 embeddings for doc %s", document_id)

            return []

        if embeddings.shape[1] != self._dim:
            raise ValueError(

                f"Embedding dimension mismatch: got {embeddings.shape[1]}, "

                f"expected {self._dim}."

            )

        with self._lock:
            if document_id in self._meta["doc_ids"]:
                logger.info("Re-indexing doc %s — removing old vectors first", document_id)

                self._remove_document_unsafe(document_id)

            normed = self._l2_normalize(embeddings)

            n = embeddings.shape[0]

            vector_ids = list(range(self._next_id, self._next_id + n))

            self._next_id += n

            ids_array = np.array(vector_ids, dtype=np.int64)

            self._index.add_with_ids(normed, ids_array)

            for vid, meta in zip(vector_ids, chunk_metadata):
                self._meta["vectors"][str(vid)] = {

                    "document_id": document_id,

                    "chunk_index": meta.get("chunk_index", 0),

                    "chunk_text":  meta.get("chunk_text", ""),

                    "file_name":   meta.get("file_name", ""),

                    "category":    meta.get("category", ""),

                    "page_number": meta.get("page_number"),

                    "scope":       meta.get("scope", "company"),

                    "user_id":     meta.get("user_id"),

                }

            self._meta["doc_ids"][document_id] = vector_ids

            self._persist()

        logger.info(

            "Indexed %d chunks for doc %s (scope=%s, total vectors: %d)",

            n, document_id, chunk_metadata[0].get("scope", "company") if chunk_metadata else "?",

            self._index.ntotal,

        )

        return vector_ids

    def search(

        self,

        query_embedding: np.ndarray,

        k: int = 5,

        filter_doc_id: Optional[str] = None,

    ) -> List[SearchResult]:
        return self._run_search(

            query_embedding=query_embedding,

            k=k,

            filter_doc_id=filter_doc_id,

            filter_scope=None,

            filter_user_id=None,

            filter_company_doc_ids=None,

        )

    def search_scoped(

        self,

        query_embedding: np.ndarray,

        scope: str,

        user_id: Optional[str] = None,

        company_doc_ids: Optional[List[str]] = None,

        k: int = 5,

    ) -> List[SearchResult]:
        if scope == "workspace":
            if not user_id:
                logger.warning("search_scoped workspace called without user_id — returning empty")

                return []

            return self._run_search(

                query_embedding=query_embedding,

                k=k,

                filter_scope="workspace",

                filter_user_id=user_id,

                filter_doc_id=None,

                filter_company_doc_ids=None,

            )

        elif scope == "company":
            return self._run_search(

                query_embedding=query_embedding,

                k=k,

                filter_scope="company",

                filter_user_id=None,

                filter_doc_id=None,

                filter_company_doc_ids=company_doc_ids,

            )

        else:
            company_results = self._run_search(

                query_embedding=query_embedding,

                k=k,

                filter_scope="company",

                filter_user_id=None,

                filter_doc_id=None,

                filter_company_doc_ids=company_doc_ids,

            )

            workspace_results = self._run_search(

                query_embedding=query_embedding,

                k=k,

                filter_scope="workspace",

                filter_user_id=user_id,

                filter_doc_id=None,

                filter_company_doc_ids=None,

            ) if user_id else []

            merged = company_results + workspace_results

            merged.sort(key=lambda r: r.score, reverse=True)

            return merged[:k]

    def remove_document(self, document_id: str) -> int:
        with self._lock:
            n = self._remove_document_unsafe(document_id)

            if n > 0:
                self._persist()

        logger.info("Removed %d vectors for doc %s", n, document_id)

        return n

    def _remove_document_unsafe(self, document_id: str) -> int:
        vector_ids = self._meta["doc_ids"].get(document_id, [])

        if not vector_ids:
            return 0

        ids_to_remove = np.array(vector_ids, dtype=np.int64)

        self._index.remove_ids(ids_to_remove)  # type: ignore[arg-type]

        for vid in vector_ids:
            self._meta["vectors"].pop(str(vid), None)

        del self._meta["doc_ids"][document_id]

        return len(vector_ids)

    def get_stats(self) -> Dict[str, Any]:
        return {

            "total_vectors":   self._index.ntotal,

            "total_documents": len(self._meta["doc_ids"]),

            "dimension":       self._dim,

            "index_path":      FAISS_INDEX_FILE,

        }

    def document_is_indexed(self, document_id: str) -> bool:
        return document_id in self._meta["doc_ids"]

    def find_document_ids_by_filename(self, query: str) -> List[str]:
        if not query or not self._meta.get("vectors"):
            return []

        query_lower = query.lower()

        matched_doc_ids = set()

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

    def _run_search(

        self,

        query_embedding: np.ndarray,

        k: int,

        filter_doc_id: Optional[str],

        filter_scope: Optional[str],

        filter_user_id: Optional[str],

        filter_company_doc_ids: Optional[List[str]],

    ) -> List[SearchResult]:
        if self._index.ntotal == 0:
            return []

        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        normed_query = self._l2_normalize(query_embedding.astype(np.float32))

        with self._lock:
            has_filter = filter_doc_id or filter_scope or filter_company_doc_ids

            fetch_k = min(k * 4 if has_filter else k, self._index.ntotal)

            scores, ids = self._index.search(normed_query, fetch_k)

        results: List[SearchResult] = []

        for score, vid in zip(scores[0], ids[0]):
            if vid == -1:
                continue

            meta = self._meta["vectors"].get(str(vid))

            if not meta:
                continue

            if filter_doc_id and meta["document_id"] != filter_doc_id:
                continue

            if filter_scope and meta.get("scope", "company") != filter_scope:
                continue

            if filter_user_id and meta.get("user_id") != filter_user_id:
                continue

            if filter_company_doc_ids and meta["document_id"] not in filter_company_doc_ids:
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

                scope=meta.get("scope", "company"),

                user_id=meta.get("user_id"),

            ))

            if len(results) >= k:
                break

        return results

    def _create_index(self):
        try:
            import faiss

        except ImportError:
            raise ImportError("faiss-cpu is required. Run: pip install faiss-cpu")

        flat_index = faiss.IndexFlatIP(self._dim)

        index = faiss.IndexIDMap2(flat_index)

        return index

    def _persist(self) -> None:
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
        if not os.path.exists(FAISS_INDEX_FILE):
            logger.info("No existing FAISS index found — starting fresh.")

            return

        try:
            import faiss

            self._index = cast(Any, faiss.read_index(FAISS_INDEX_FILE))

            with open(FAISS_META_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._next_id = data.get("next_id", 0)

            self._meta["vectors"] = data.get("vectors", {})

            self._meta["doc_ids"] = data.get("doc_ids", {})

            for vid_str, meta in self._meta["vectors"].items():
                if "scope" not in meta:
                    meta["scope"] = "company"

                if "user_id" not in meta:
                    meta["user_id"] = None

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

    @staticmethod

    def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)

        norms = np.where(norms == 0, 1e-10, norms)

        return (vectors / norms).astype(np.float32)

_store_instance: Optional[FAISSVectorStore] = None

def get_vector_store() -> FAISSVectorStore:
    global _store_instance

    if _store_instance is None:
        _store_instance = FAISSVectorStore()

    return _store_instance

def reset_vector_store() -> None:
    global _store_instance

    _store_instance = None
