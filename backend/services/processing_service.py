"""
backend/services/processing_service.py
─────────────────────────────────────────────────────────────
Module 4 processing pipeline orchestrator.

Pipeline per document:
  1. Fetch metadata from Supabase documents table
  2. Update status → Processing
  3. Download file bytes from Supabase Storage
  4. Extract text (loaders.py)
  5. Clean text (preprocessor.py)
  6. Chunk text (chunker.py) → List[ChunkData]
  7. Generate embeddings (embedder.py) → np.ndarray
  8. Add to FAISS index (vector_store.py)
  9. Save chunk rows to document_chunks table
  10. Update status → Indexed
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import time
import logging
import traceback
from typing import List, Optional, Dict, Any

from database.supabase_client import get_supabase, BUCKET_NAME
from database.chunk_repository import (
    save_chunks,
    delete_chunks,
    get_chunk_count_for_user,
    get_chunk_counts_per_document,
)
from models.document import DocumentStatus
from models.processing import (
    DocumentProcessingResult,
    ProcessAllResponse,
)
from processing.loaders import load_document, LoadedDocument
from processing.preprocessor import preprocess_text, get_text_stats
from processing.chunker import chunk_text, build_page_map
from processing.embedder import get_embedder
from processing.vector_store import get_vector_store

logger = logging.getLogger(__name__)


# ── Status helpers ────────────────────────────────────────────

def _update_status(doc_id: str, status: DocumentStatus) -> None:
    """Update a document's processing status in Supabase."""
    get_supabase().table("documents").update(
        {"status": status.value}
    ).eq("id", doc_id).execute()
    logger.info("Doc %s → %s", doc_id, status.value)


def _get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single document row by ID."""
    result = (
        get_supabase()
        .table("documents")
        .select("*")
        .eq("id", doc_id)
        .single()
        .execute()
    )
    return result.data


# ── File download ─────────────────────────────────────────────

def _download_file(storage_path: str) -> bytes:
    """Download a file from Supabase Storage."""
    supabase = get_supabase()
    response = supabase.storage.from_(BUCKET_NAME).download(storage_path)

    if not response:
        raise RuntimeError(
            f"Empty response when downloading '{storage_path}' from storage."
        )

    return response


# ── Core pipeline ─────────────────────────────────────────────

async def process_document(
    doc_id: str,
    user_id: str,
    force_reindex: bool = False,
) -> DocumentProcessingResult:
    """Run the full processing pipeline for one document."""
    start_time = time.time()
    doc = _get_document(doc_id)

    if not doc:
        return DocumentProcessingResult(
            document_id=doc_id,
            file_name="unknown",
            status="failed",
            error="Document not found in database.",
        )

    file_name = doc["file_name"]
    file_type = doc["file_type"]
    storage_path = doc["storage_path"]
    category = doc.get("category", "General")

    if doc["status"] == DocumentStatus.INDEXED.value and not force_reindex:
        logger.info("Skipping already-indexed doc: %s", file_name)
        return DocumentProcessingResult(
            document_id=doc_id,
            file_name=file_name,
            status="skipped",
        )

    try:
        logger.info("▶ Processing: %s (%s)", file_name, file_type)

        _update_status(doc_id, DocumentStatus.PROCESSING)

        file_bytes = _download_file(storage_path)

        loaded: LoadedDocument = load_document(file_bytes, file_type)
        if not loaded.full_text.strip():
            raise ValueError(f"No text could be extracted from '{file_name}'.")

        clean_text = preprocess_text(loaded.full_text)
        if not clean_text:
            raise ValueError(f"Text was empty after preprocessing '{file_name}'.")

        page_map = build_page_map(loaded.pages) if loaded.pages else None
        chunks = chunk_text(clean_text, page_map=page_map)
        if not chunks:
            raise ValueError(f"No chunks produced from '{file_name}'.")

        embedder = get_embedder()
        chunk_texts = [c.chunk_text for c in chunks]
        embeddings = embedder.embed_texts(
            chunk_texts,
            task_type="retrieval_document",
            title=file_name,
        )

        vector_store = get_vector_store()
        if vector_store.document_is_indexed(doc_id):
            vector_store.remove_document(doc_id)
            delete_chunks(doc_id)

        chunk_meta_list = [
            {
                "chunk_index": c.chunk_index,
                "chunk_text": c.chunk_text,
                "file_name": file_name,
                "category": category,
                "page_number": c.page_number,
            }
            for c in chunks
        ]
        vector_ids = vector_store.add_chunks(doc_id, embeddings, chunk_meta_list)

        chunk_rows = [
            {
                "chunk_index": c.chunk_index,
                "chunk_text": c.chunk_text,
                "page_number": c.page_number,
                "token_count": c.token_count,
            }
            for c in chunks
        ]
        save_chunks(chunk_rows, doc_id, user_id, category)

        _update_status(doc_id, DocumentStatus.INDEXED)

        elapsed = time.time() - start_time
        logger.info(
            "✅ Indexed '%s': %d chunks, %d vectors in %.2fs",
            file_name, len(chunks), len(vector_ids), elapsed,
        )

        return DocumentProcessingResult(
            document_id=doc_id,
            file_name=file_name,
            status="indexed",
            chunks_created=len(chunks),
            vectors_added=len(vector_ids),
            processing_time_seconds=round(elapsed, 2),
        )

    except Exception as exc:
        elapsed = time.time() - start_time
        error_detail = traceback.format_exc()
        logger.error(
            "❌ Processing failed for '%s': %s\n%s",
            file_name, exc, error_detail,
        )
        _update_status(doc_id, DocumentStatus.FAILED)

        return DocumentProcessingResult(
            document_id=doc_id,
            file_name=file_name,
            status="failed",
            error=str(exc),
            processing_time_seconds=round(elapsed, 2),
        )


# ── Batch processing ──────────────────────────────────────────

async def process_all_pending(
    user_id: str,
    force_reindex: bool = False,
) -> ProcessAllResponse:
    """Process all documents for a user that are in Uploaded or Failed status."""
    start_time = time.time()
    supabase = get_supabase()

    statuses_to_process = [
        DocumentStatus.UPLOADED.value,
        DocumentStatus.FAILED.value,
    ]
    if force_reindex:
        statuses_to_process.append(DocumentStatus.INDEXED.value)

    result = (
        supabase.table("documents")
        .select("id, file_name, status")
        .eq("user_id", user_id)
        .in_("status", statuses_to_process)
        .execute()
    )

    docs = result.data or []

    results: List[DocumentProcessingResult] = []
    indexed = failed = skipped = 0

    for doc in docs:
        outcome = await process_document(
            doc_id=doc["id"],
            user_id=user_id,
            force_reindex=force_reindex,
        )
        results.append(outcome)

        if outcome.status == "indexed":
            indexed += 1
        elif outcome.status == "failed":
            failed += 1
        elif outcome.status == "skipped":
            skipped += 1

    total_time = round(time.time() - start_time, 2)

    return ProcessAllResponse(
        success=failed == 0,
        total_documents=len(docs),
        indexed=indexed,
        failed=failed,
        skipped=skipped,
        results=results,
        total_time_seconds=total_time,
    )


# ── Delete index ──────────────────────────────────────────────

async def deindex_document(doc_id: str, user_id: str) -> tuple[int, int]:
    """Remove a document's vectors from FAISS and chunks from Supabase."""
    vector_store = get_vector_store()
    vectors_removed = vector_store.remove_document(doc_id)
    chunks_removed = delete_chunks(doc_id)

    _update_status(doc_id, DocumentStatus.UPLOADED)

    return vectors_removed, chunks_removed


# ── Status / stats ────────────────────────────────────────────

async def get_indexing_stats(user_id: str) -> Dict[str, Any]:
    """Returns comprehensive indexing statistics for a user."""
    supabase = get_supabase()

    docs_result = (
        supabase.table("documents")
        .select("id, file_name, status, uploaded_at")
        .eq("user_id", user_id)
        .execute()
    )
    docs = docs_result.data or []

    doc_ids = [d["id"] for d in docs]
    chunk_counts = get_chunk_counts_per_document(doc_ids)

    vector_store = get_vector_store()
    faiss_stats = vector_store.get_stats()

    status_counts = {"Uploaded": 0, "Processing": 0, "Indexed": 0, "Failed": 0}
    document_statuses = []

    for doc in docs:
        s = doc["status"]
        if s in status_counts:
            status_counts[s] += 1

        document_statuses.append({
            "document_id": doc["id"],
            "file_name": doc["file_name"],
            "status": s,
            "chunks_in_db": chunk_counts.get(doc["id"], 0),
            "vectors_in_faiss": vector_store.document_is_indexed(doc["id"]),
            "uploaded_at": doc.get("uploaded_at"),
        })

    total_chunks = sum(chunk_counts.values())

    return {
        "user_id": user_id,
        "total_documents": len(docs),
        "indexed_count": status_counts["Indexed"],
        "processing_count": status_counts["Processing"],
        "failed_count": status_counts["Failed"],
        "uploaded_count": status_counts["Uploaded"],
        "total_chunks": total_chunks,
        "total_vectors_in_faiss": faiss_stats["total_vectors"],
        "documents": document_statuses,
    }
