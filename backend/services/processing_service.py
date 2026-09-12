from __future__ import annotations

import time

import logging

import traceback

from typing import List, Optional, Dict, Any, cast

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

def _update_status(doc_id: str, status: DocumentStatus) -> None:
    get_supabase().table("documents").update(

        {"status": status.value}

    ).eq("id", doc_id).execute()

    logger.info("Doc %s → %s", doc_id, status.value)

def _get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    result = (

        get_supabase()

        .table("documents")

        .select("*")

        .eq("id", doc_id)

        .single()

        .execute()

    )

    data = result.data
    if isinstance(data, dict):
        return data
    return None

def _download_file(storage_path: str) -> bytes:
    supabase = get_supabase()

    response = supabase.storage.from_(BUCKET_NAME).download(storage_path)

    if not response:
        raise RuntimeError(

            f"Empty response when downloading '{storage_path}' from storage."

        )

    return response

async def process_document(

    doc_id: str,

    user_id: str,

    force_reindex: bool = False,

) -> DocumentProcessingResult:
    start_time = time.time()

    doc = _get_document(doc_id)

    if not doc:
        return DocumentProcessingResult(

            document_id=doc_id,

            file_name="unknown",

            status="failed",

            error="Document not found in database.",

        )

    file_name    = doc["file_name"]

    file_type    = doc["file_type"]

    storage_path = doc["storage_path"]

    category     = doc.get("category", "General")

    scope        = doc.get("scope", "company")

    company_id   = doc.get("company_id")

    if doc["status"] == DocumentStatus.INDEXED.value and not force_reindex:
        logger.info("Skipping already-indexed doc: %s", file_name)

        return DocumentProcessingResult(

            document_id=doc_id,

            file_name=file_name,

            status="skipped",

        )

    try:
        logger.info("▶ Processing: %s (%s) [scope=%s]", file_name, file_type, scope)

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

                "chunk_text":  c.chunk_text,

                "file_name":   file_name,

                "category":    category,

                "page_number": c.page_number,

                "scope":       scope,

                "user_id":     user_id if scope == "workspace" else None,

            }

            for c in chunks

        ]

        vector_ids = vector_store.add_chunks(doc_id, embeddings, chunk_meta_list)

        chunk_rows = [

            {

                "chunk_index": c.chunk_index,

                "chunk_text":  c.chunk_text,

                "page_number": c.page_number,

                "token_count": c.token_count,

            }

            for c in chunks

        ]

        save_chunks(

            chunks=chunk_rows,

            document_id=doc_id,

            user_id=user_id,

            category=category,

            scope=scope,

            company_id=company_id,

        )

        _update_status(doc_id, DocumentStatus.INDEXED)

        if scope == "company" and company_id:
            try:
                from services.notification_service import get_notification_service
                event_type = "updated" if force_reindex else "added"
                await get_notification_service().notify_company_document_change(
                    company_id=str(company_id),
                    document_id=doc_id,
                    file_name=file_name,
                    change_type=event_type,
                    actor_user_id=user_id,
                )
            except Exception as notif_err:
                logger.error("Notification hook error for doc %s: %s", doc_id, notif_err)

        elapsed = time.time() - start_time

        logger.info(

            "✅ Indexed '%s': %d chunks, %d vectors in %.2fs [scope=%s]",

            file_name, len(chunks), len(vector_ids), elapsed, scope,

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

async def process_all_pending(

    user_id: str,

    force_reindex: bool = False,

) -> ProcessAllResponse:
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

    docs = cast(List[Dict[str, Any]], result.data or [])

    results: List[DocumentProcessingResult] = []

    indexed = failed = skipped = 0

    for doc in docs:
        outcome = await process_document(

            doc_id=str(doc.get("id", "")),

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

async def deindex_document(doc_id: str, user_id: str) -> tuple[int, int]:
    vector_store = get_vector_store()

    vectors_removed = vector_store.remove_document(doc_id)

    chunks_removed = delete_chunks(doc_id)

    _update_status(doc_id, DocumentStatus.UPLOADED)

    return vectors_removed, chunks_removed

async def get_indexing_stats(user_id: str) -> Dict[str, Any]:
    supabase = get_supabase()

    docs_result = (

        supabase.table("documents")

        .select("id, file_name, status, scope, uploaded_at")

        .eq("user_id", user_id)

        .execute()

    )

    docs = cast(List[Dict[str, Any]], docs_result.data or [])

    doc_ids: List[str] = [str(d.get("id", "")) for d in docs if d.get("id")]

    chunk_counts = get_chunk_counts_per_document(doc_ids)

    vector_store = get_vector_store()

    faiss_stats = vector_store.get_stats()

    status_counts = {"Uploaded": 0, "Processing": 0, "Indexed": 0, "Failed": 0}

    document_statuses = []

    for doc in docs:
        s = str(doc.get("status", "Uploaded"))

        if s in status_counts:
            status_counts[s] += 1

        d_id = str(doc.get("id", ""))
        document_statuses.append({

            "document_id":      d_id,

            "file_name":        doc.get("file_name", "Document"),

            "status":           s,

            "scope":            doc.get("scope", "company"),

            "chunks_in_db":     chunk_counts.get(d_id, 0),

            "vectors_in_faiss": vector_store.document_is_indexed(d_id),

            "uploaded_at":      doc.get("uploaded_at"),

        })

    total_chunks = sum(chunk_counts.values())

    return {

        "user_id":               user_id,

        "total_documents":       len(docs),

        "indexed_count":         status_counts["Indexed"],

        "processing_count":      status_counts["Processing"],

        "failed_count":          status_counts["Failed"],

        "uploaded_count":        status_counts["Uploaded"],

        "total_chunks":          total_chunks,

        "total_vectors_in_faiss": faiss_stats["total_vectors"],

        "documents":             document_statuses,

    }
