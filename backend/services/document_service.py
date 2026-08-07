"""
backend/services/document_service.py
─────────────────────────────────────────────────────────────
Business logic for document operations.
Called by the API router (api/documents.py).
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import os
import re
import time
import logging
from typing import Optional, Tuple, Any, Dict, List

from fastapi import UploadFile, HTTPException, status, BackgroundTasks

from database.supabase_client import get_supabase, BUCKET_NAME
from models.document import DocumentCategory, DocumentStatus

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "text/plain": "TXT",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


# ── Helpers ───────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def _get_file_type_label(filename: str) -> str:
    ext = _get_extension(filename)
    labels = {".pdf": "PDF", ".docx": "DOCX", ".txt": "TXT"}
    return labels.get(ext, ext.lstrip(".").upper())


def _sanitize_filename(filename: str) -> str:
    """Remove special characters from filename for safe storage paths."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", filename)


def _build_storage_path(user_id: str, filename: str) -> str:
    """
    Builds the Supabase Storage object path.
    Convention: {user_id}/{timestamp}_{sanitized_filename}
    """
    sanitized = _sanitize_filename(filename)
    return f"{user_id}/{int(time.time() * 1000)}_{sanitized}"


# ── Validation ────────────────────────────────────────────────

async def validate_file(file: UploadFile) -> Tuple[bytes, str]:
    """
    Validates the uploaded file for type and size.
    Returns (file_bytes, file_type_label) or raises HTTPException.
    """
    ext = _get_extension(file.filename or "")
    content_type = file.content_type or ""

    if ext not in ALLOWED_EXTENSIONS and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT.",
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        size_mb = len(content) / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed: 20 MB.",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File appears to be empty.",
        )

    file_type = _get_file_type_label(file.filename or "")
    return content, file_type


# ── Duplicate Check ───────────────────────────────────────────

async def check_duplicate(
    filename: str, file_size: int, user_id: str
) -> bool:
    """Returns True if user already has a file with the same name+size."""
    supabase = get_supabase()
    result = (
        supabase.table("documents")
        .select("id")
        .eq("user_id", user_id)
        .eq("file_name", filename)
        .eq("file_size", file_size)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


# ── Upload ────────────────────────────────────────────────────

async def upload_document(
    file: UploadFile,
    category: str,
    user_id: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Dict[str, Any]:
    """
    Full upload pipeline:
      1. Validate file (type, size)
      2. Duplicate check
      3. Upload to Supabase Storage
      4. Insert metadata into documents table
      5. Trigger background processing (Module 4)

    Returns: document metadata dict
    Raises:  HTTPException on failure
    """
    # 1. Validate
    content, file_type = await validate_file(file)

    # 2. Duplicate check
    is_dup = await check_duplicate(file.filename or "", len(content), user_id)
    if is_dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A file named '{file.filename}' with the same size already exists.",
        )

    # 3. Build storage path and upload
    storage_path = _build_storage_path(user_id, file.filename or "unnamed")
    supabase = get_supabase()

    storage_result = supabase.storage.from_(BUCKET_NAME).upload(
        path=storage_path,
        file=content,
        file_options={
            "content-type": file.content_type or "application/octet-stream",
            "cache-control": "3600",
            "upsert": "false",
        },
    )

    if hasattr(storage_result, "error") and storage_result.error:
        logger.error("Storage upload failed: %s", storage_result.error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage upload failed: {storage_result.error}",
        )

    # 4. Insert metadata
    insert_result = (
        supabase.table("documents")
        .insert(
            {
                "user_id": user_id,
                "file_name": file.filename,
                "file_type": file_type,
                "file_size": len(content),
                "storage_path": storage_path,
                "category": category,
                "status": DocumentStatus.UPLOADED.value,
            }
        )
        .execute()
    )

    if not insert_result.data:
        # Roll back storage upload
        supabase.storage.from_(BUCKET_NAME).remove([storage_path])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save document metadata.",
        )

    doc = insert_result.data[0]
    logger.info("Document uploaded: %s (id=%s)", file.filename, doc["id"])

    # 5. Module 4: Trigger background processing
    if background_tasks is not None:
        from services.processing_service import process_document
        background_tasks.add_task(
            process_document,
            doc_id=doc["id"],
            user_id=user_id,
            force_reindex=False,
        )
        logger.info("Processing queued for doc %s", doc["id"])

    return doc


# ── List ──────────────────────────────────────────────────────

async def list_documents(
    user_id: str,
    page: int = 1,
    page_size: int = 50,
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    """Returns (documents, total_count) for a user with optional filters."""
    supabase = get_supabase()

    query = (
        supabase.table("documents")
        .select("*", count="exact")
        .eq("user_id", user_id)
        .order("uploaded_at", desc=True)
    )

    if category and category != "All":
        query = query.eq("category", category)
    if status_filter and status_filter != "All":
        query = query.eq("status", status_filter)

    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)

    result = query.execute()
    total = result.count if hasattr(result, "count") and result.count else len(result.data)

    return result.data, total


# ── Get Single ────────────────────────────────────────────────

async def get_document(doc_id: str, user_id: str) -> Dict[str, Any]:
    """Fetches a single document (scoped to user)."""
    supabase = get_supabase()
    result = (
        supabase.table("documents")
        .select("*")
        .eq("id", doc_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return result.data


# ── Delete ────────────────────────────────────────────────────

async def delete_document(doc_id: str, user_id: str) -> None:
    """Deletes a document from Storage and removes the metadata row."""
    supabase = get_supabase()

    doc = await get_document(doc_id, user_id)

    # Remove from storage
    supabase.storage.from_(BUCKET_NAME).remove([doc["storage_path"]])

    # Delete metadata row
    supabase.table("documents").delete().eq("id", doc_id).execute()
    logger.info("Document deleted: id=%s", doc_id)


# ── Update Status ─────────────────────────────────────────────

async def update_document_status(doc_id: str, new_status: DocumentStatus) -> None:
    """Updates a document's processing status."""
    supabase = get_supabase()
    supabase.table("documents").update({"status": new_status.value}).eq("id", doc_id).execute()
    logger.info("Document %s status → %s", doc_id, new_status.value)
