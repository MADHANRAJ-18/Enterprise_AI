from __future__ import annotations

import os

import re

import time

import logging

from typing import Optional, Tuple, Any, Dict, List, cast

from fastapi import UploadFile, HTTPException, status, BackgroundTasks

from postgrest.types import CountMethod

from database.supabase_client import get_supabase, BUCKET_NAME

from models.document import DocumentCategory, DocumentStatus, DocumentScope

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

ALLOWED_CONTENT_TYPES = {

    "application/pdf": "PDF",

    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",

    "text/plain": "TXT",

    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",

    "application/vnd.ms-powerpoint": "PPTX",

}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".pptx"}

def _get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()

def _get_file_type_label(filename: str) -> str:
    ext = _get_extension(filename)

    labels = {".pdf": "PDF", ".docx": "DOCX", ".txt": "TXT", ".pptx": "PPTX"}

    return labels.get(ext, ext.lstrip(".").upper())

def _sanitize_filename(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

def _build_storage_path(user_id: str, filename: str, scope: str) -> str:
    sanitized = _sanitize_filename(filename)

    return f"{user_id}/{scope}/{int(time.time() * 1000)}_{sanitized}"

def _require_role_for_scope(user_id: str, scope: str) -> None:
    if scope != DocumentScope.COMPANY.value:
        return

    supabase = get_supabase()

    result = (

        supabase.table("user_profiles")

        .select("role")

        .eq("user_id", user_id)

        .limit(1)

        .execute()

    )

    data = result.data

    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail="User profile not found. Cannot verify role for company document upload.",

        )

    row = data[0]

    role = str(row.get("role", "employee"))

    if role != "knowledge_admin":
        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail=(

                "Only Knowledge Admins can upload company documents. "

                "To upload private documents, use scope='workspace'."

            ),

        )

def _get_user_company_id(user_id: str) -> Optional[str]:
    supabase = get_supabase()

    result = (

        supabase.table("user_profiles")

        .select("company_id")

        .eq("user_id", user_id)

        .limit(1)

        .execute()

    )

    data = result.data

    if isinstance(data, list) and data and isinstance(data[0], dict):
        company_id = data[0].get("company_id")

        return str(company_id) if company_id else None

    return None

async def validate_file(file: UploadFile) -> Tuple[bytes, str]:
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

async def check_duplicate(

    filename: str, file_size: int, user_id: str, scope: str = "workspace"

) -> bool:
    supabase = get_supabase()

    query = (

        supabase.table("documents")

        .select("id")

        .eq("user_id", user_id)

        .eq("file_name", filename)

        .eq("file_size", file_size)

        .eq("scope", scope)

        .limit(1)

    )

    result = query.execute()

    return isinstance(result.data, list) and len(result.data) > 0

async def upload_document(

    file: UploadFile,

    category: str,

    user_id: str,

    background_tasks: Optional[BackgroundTasks] = None,

    scope: str = "workspace",

    company_id: Optional[str] = None,

) -> Dict[str, Any]:
    _require_role_for_scope(user_id, scope)

    content, file_type = await validate_file(file)

    is_dup = await check_duplicate(file.filename or "", len(content), user_id, scope)

    if is_dup:
        raise HTTPException(

            status_code=status.HTTP_409_CONFLICT,

            detail=f"A file named '{file.filename}' with the same size already exists in {scope} scope.",

        )

    if company_id is None:
        company_id = _get_user_company_id(user_id)

    storage_path = _build_storage_path(user_id, file.filename or "unnamed", scope)

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

    insert_result = (

        supabase.table("documents")

        .insert(

            {

                "user_id":     user_id,

                "file_name":   file.filename,

                "file_type":   file_type,

                "file_size":   len(content),

                "storage_path": storage_path,

                "category":    category,

                "status":      DocumentStatus.UPLOADED.value,

                "scope":       scope,

                "company_id":  company_id,

            }

        )

        .execute()

    )

    data = insert_result.data

    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        supabase.storage.from_(BUCKET_NAME).remove([storage_path])

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail="Failed to save document metadata.",

        )

    doc: Dict[str, Any] = data[0]

    doc_id = str(doc.get("id", ""))

    logger.info(

        "Document uploaded: %s (id=%s, scope=%s)",

        file.filename, doc_id, scope,

    )

    if background_tasks is not None:
        from services.processing_service import process_document

        background_tasks.add_task(

            process_document,

            doc_id=doc_id,

            user_id=user_id,

            force_reindex=False,

        )

        logger.info("Processing queued for doc %s", doc_id)

    return doc

async def list_documents(

    user_id: str,

    page: int = 1,

    page_size: int = 50,

    category: Optional[str] = None,

    status_filter: Optional[str] = None,

    scope: Optional[str] = None,

) -> Tuple[List[Dict[str, Any]], int]:
    supabase = get_supabase()

    query = (

        supabase.table("documents")

        .select("*", count=CountMethod.exact)

        .eq("user_id", user_id)

        .order("uploaded_at", desc=True)

    )

    if scope and scope != "both":
        query = query.eq("scope", scope)

    if category and category != "All":
        query = query.eq("category", category)

    if status_filter and status_filter != "All":
        query = query.eq("status", status_filter)

    offset = (page - 1) * page_size

    query = query.range(offset, offset + page_size - 1)

    result = query.execute()

    raw_data = result.data if isinstance(result.data, list) else []

    docs: List[Dict[str, Any]] = [d for d in raw_data if isinstance(d, dict)]

    total = result.count if hasattr(result, "count") and result.count is not None else len(docs)

    return docs, total

async def list_company_documents(

    company_id: str,

    page: int = 1,

    page_size: int = 50,

    category: Optional[str] = None,

    status_filter: Optional[str] = None,

) -> Tuple[List[Dict[str, Any]], int]:
    supabase = get_supabase()

    query = (

        supabase.table("documents")

        .select("*", count=CountMethod.exact)

        .eq("scope", "company")

        .eq("company_id", company_id)

        .order("uploaded_at", desc=True)

    )

    if category and category != "All":
        query = query.eq("category", category)

    if status_filter and status_filter != "All":
        query = query.eq("status", status_filter)

    offset = (page - 1) * page_size

    query = query.range(offset, offset + page_size - 1)

    result = query.execute()

    raw_data = result.data if isinstance(result.data, list) else []

    docs: List[Dict[str, Any]] = [d for d in raw_data if isinstance(d, dict)]

    total = result.count if hasattr(result, "count") and result.count is not None else len(docs)

    return docs, total

async def get_document(doc_id: str, user_id: str) -> Dict[str, Any]:
    supabase = get_supabase()
    try:
        result = (
            supabase.table("documents")
            .select("*")
            .eq("id", doc_id)
            .execute()
        )
    except Exception as exc:
        logger.warning("Failed to query document %s: %s", doc_id, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    data = result.data
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    doc = data[0]
    scope = doc.get("scope", "workspace")
    doc_user_id = str(doc.get("user_id", ""))

    if scope == "workspace" and doc_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to private workspace document.")

    return doc

async def get_document_signed_url(doc_id: str, user_id: str, expiry_seconds: int = 900) -> Dict[str, Any]:
    doc = await get_document(doc_id, user_id)
    scope = doc.get("scope", "workspace")
    if scope == "company":
        user_company = _get_user_company_id(user_id)
        doc_company = doc.get("company_id")
        if doc_company and user_company and str(doc_company) != user_company:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to company document.")

    storage_path = str(doc.get("storage_path", ""))
    if not storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File storage path not found.")

    supabase = get_supabase()
    signed_res: Any = supabase.storage.from_(BUCKET_NAME).create_signed_url(storage_path, expiry_seconds)
    url: Optional[str] = None
    if isinstance(signed_res, dict):
        res_data = signed_res.get("data")
        data_url = res_data.get("signedUrl") if isinstance(res_data, dict) else None
        url = signed_res.get("signedURL") or signed_res.get("signedUrl") or data_url
    elif hasattr(signed_res, "signed_url"):
        url = getattr(signed_res, "signed_url", None)

    return {
        "success": True,
        "document_id": doc_id,
        "file_name": doc.get("file_name", "document.pdf"),
        "file_type": doc.get("file_type", "PDF"),
        "scope": scope,
        "storage_path": storage_path,
        "signed_url": url,
    }

async def get_document_file_stream(doc_id: str, user_id: str) -> Tuple[bytes, str, str]:
    doc = await get_document(doc_id, user_id)
    scope = doc.get("scope", "workspace")
    if scope == "company":
        user_company = _get_user_company_id(user_id)
        doc_company = doc.get("company_id")
        if doc_company and user_company and str(doc_company) != user_company:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to company document.")

    storage_path = str(doc.get("storage_path", ""))
    if not storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File storage path not found.")

    supabase = get_supabase()
    file_bytes = supabase.storage.from_(BUCKET_NAME).download(storage_path)
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to retrieve file contents from storage.")

    content_type = "application/pdf" if str(doc.get("file_type", "")).upper() == "PDF" else "application/octet-stream"
    return file_bytes, str(doc.get("file_name", "document.pdf")), content_type

async def update_document_metadata(doc_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    supabase = get_supabase()

    doc = await get_document(doc_id, user_id)

    scope = doc.get("scope", "workspace")

    _require_role_for_scope(user_id, scope)

    allowed_updates = {}

    if "category" in updates and updates["category"] is not None:
        if isinstance(updates["category"], str):
            allowed_updates["category"] = updates["category"]

        else:
            allowed_updates["category"] = updates["category"].value

    if "file_name" in updates and updates["file_name"] is not None:
        allowed_updates["file_name"] = updates["file_name"]

    if not allowed_updates:
        return doc

    result = (

        supabase.table("documents")

        .update(allowed_updates)

        .eq("id", doc_id)

        .execute()

    )

    updated_row = cast(list, result.data or [doc])[0]

    company_id = doc.get("company_id")
    if scope == "company" and company_id:
        try:
            from services.notification_service import get_notification_service
            await get_notification_service().notify_company_document_change(
                company_id=str(company_id),
                document_id=doc_id,
                file_name=updated_row.get("file_name", doc.get("file_name", "unnamed")),
                change_type="updated",
                actor_user_id=user_id,
            )
        except Exception as notif_err:
            logger.error("Notification hook error on update doc %s: %s", doc_id, notif_err)

    return updated_row

async def overwrite_document(

    doc_id: str,

    user_id: str,

    file: UploadFile,

    background_tasks: Optional[BackgroundTasks] = None,

) -> Dict[str, Any]:
    import datetime

    supabase = get_supabase()

    existing_doc = await get_document(doc_id, user_id)

    scope = str(existing_doc.get("scope", "workspace"))

    _require_role_for_scope(user_id, scope)

    content, file_type = await validate_file(file)

    try:
        from processing.vector_store import get_vector_store

        vstore = get_vector_store()

        vstore.remove_document(doc_id)

    except Exception as exc:
        logger.warning("FAISS vector removal warning during overwrite: %s", exc)

    try:
        from database.chunk_repository import delete_chunks

        delete_chunks(doc_id)

    except Exception as exc:
        logger.warning("Chunk DB deletion warning during overwrite: %s", exc)

    old_storage_path = str(existing_doc.get("storage_path", ""))

    if old_storage_path:
        try:
            supabase.storage.from_(BUCKET_NAME).remove([old_storage_path])

        except Exception as exc:
            logger.warning("Old storage file removal warning: %s", exc)

    new_storage_path = _build_storage_path(user_id, file.filename or "unnamed", scope)

    storage_result = supabase.storage.from_(BUCKET_NAME).upload(

        path=new_storage_path,

        file=content,

        file_options={

            "content-type": file.content_type or "application/octet-stream",

            "cache-control": "3600",

            "upsert": "true",

        },

    )

    if hasattr(storage_result, "error") and storage_result.error:
        logger.error("Storage upload failed during overwrite: %s", storage_result.error)

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Storage upload failed: {storage_result.error}",

        )

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    update_payload = {

        "file_name": file.filename,

        "file_type": file_type,

        "file_size": len(content),

        "storage_path": new_storage_path,

        "status": DocumentStatus.UPLOADED.value,

        "uploaded_at": now_iso,

    }

    result = (

        supabase.table("documents")

        .update(update_payload)

        .eq("id", doc_id)

        .execute()

    )

    data = result.data

    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail="Failed to update document metadata during overwrite.",

        )

    updated_doc: Dict[str, Any] = data[0]

    logger.info("Document content overwritten: doc_id=%s file=%s", doc_id, file.filename)

    if background_tasks is not None:
        from services.processing_service import process_document

        background_tasks.add_task(

            process_document,

            doc_id=doc_id,

            user_id=user_id,

            force_reindex=True,

        )

        logger.info("Processing re-queued for overwritten doc %s", doc_id)

    return updated_doc

async def delete_document(doc_id: str, user_id: str) -> None:
    supabase = get_supabase()

    doc = await get_document(doc_id, user_id)

    scope = str(doc.get("scope", "workspace"))

    file_name = str(doc.get("file_name", "unnamed"))
    company_id = doc.get("company_id")

    # Remove from FAISS index and chunk database
    try:
        from processing.vector_store import get_vector_store
        get_vector_store().remove_document(doc_id)
    except Exception as v_err:
        logger.warning("FAISS vector removal warning on delete doc %s: %s", doc_id, v_err)

    try:
        from database.chunk_repository import delete_chunks
        delete_chunks(doc_id)
    except Exception as c_err:
        logger.warning("Chunk DB deletion warning on delete doc %s: %s", doc_id, c_err)

    storage_path = str(doc.get("storage_path", ""))

    if storage_path:
        supabase.storage.from_(BUCKET_NAME).remove([storage_path])

    supabase.table("documents").delete().eq("id", doc_id).execute()

    logger.info("Document deleted: id=%s scope=%s", doc_id, scope)

    if scope == "company" and company_id:
        try:
            from services.notification_service import get_notification_service
            await get_notification_service().notify_company_document_change(
                company_id=str(company_id),
                document_id=doc_id,
                file_name=file_name,
                change_type="removed",
                actor_user_id=user_id,
            )
        except Exception as notif_err:
            logger.error("Notification hook error on delete doc %s: %s", doc_id, notif_err)

async def update_document_status(doc_id: str, new_status: DocumentStatus) -> None:
    supabase = get_supabase()

    supabase.table("documents").update({"status": new_status.value}).eq("id", doc_id).execute()

    logger.info("Document %s status → %s", doc_id, new_status.value)
