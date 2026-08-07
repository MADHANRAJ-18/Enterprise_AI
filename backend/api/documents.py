"""
backend/api/documents.py
─────────────────────────────────────────────────────────────
REST API endpoints for Document Upload & Management.
─────────────────────────────────────────────────────────────
"""

from typing import Optional
from fastapi import (
    APIRouter, UploadFile, File, Form, Query, BackgroundTasks,
    HTTPException, status as http_status
)

from services.document_service import (
    upload_document,
    list_documents,
    get_document,
    delete_document,
    update_document_status,
)
from models.document import (
    DocumentCategory,
    DocumentStatus,
    DocumentListResponse,
    UploadResponse,
    DeleteResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


# ── POST /api/documents/upload ────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Upload a document",
    responses={
        409: {"model": ErrorResponse, "description": "Duplicate file"},
        413: {"model": ErrorResponse, "description": "File too large"},
        415: {"model": ErrorResponse, "description": "Unsupported file type"},
    },
)
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload (PDF, DOCX, TXT, ≤ 20 MB)"),
    category: DocumentCategory = Form(DocumentCategory.GENERAL),
    user_id: str = Form(..., description="Authenticated user UUID"),
):
    """
    Upload a document to Supabase Storage and save metadata.
    Auto-triggers Module 4 processing in background.
    """
    doc = await upload_document(
        file=file,
        category=category.value,
        user_id=user_id,
        background_tasks=background_tasks,
    )
    return UploadResponse(
        success=True,
        document=doc,
        message=f"'{file.filename}' uploaded successfully.",
    )


# ── GET /api/documents ────────────────────────────────────────

@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents for a user",
)
async def list_user_documents(
    user_id: str = Query(..., description="Authenticated user UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    doc_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
):
    """Returns all documents for the authenticated user."""
    docs, total = await list_documents(
        user_id=user_id,
        page=page,
        page_size=page_size,
        category=category,
        status_filter=doc_status,
    )
    return DocumentListResponse(
        documents=docs,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /api/documents/{id} ───────────────────────────────────

@router.get(
    "/{doc_id}",
    summary="Get a single document",
    responses={404: {"model": ErrorResponse}},
)
async def get_single_document(
    doc_id: str,
    user_id: str = Query(..., description="Authenticated user UUID"),
):
    """Retrieve a single document's metadata by ID."""
    doc = await get_document(doc_id=doc_id, user_id=user_id)
    return doc


# ── DELETE /api/documents/{id} ────────────────────────────────

@router.delete(
    "/{doc_id}",
    response_model=DeleteResponse,
    summary="Delete a document",
    responses={404: {"model": ErrorResponse}},
)
async def delete(
    doc_id: str,
    user_id: str = Query(..., description="Authenticated user UUID"),
):
    """Deletes a document from Supabase Storage and removes its metadata row."""
    await delete_document(doc_id=doc_id, user_id=user_id)
    return DeleteResponse(success=True, message="Document deleted successfully.")


# ── PATCH /api/documents/{id}/status ──────────────────────────

@router.patch(
    "/{doc_id}/status",
    summary="Update document processing status",
    responses={404: {"model": ErrorResponse}},
)
async def update_status(
    doc_id: str,
    new_status: DocumentStatus,
    user_id: str = Query(..., description="Authenticated user UUID"),
):
    """Updates the processing status of a document."""
    await update_document_status(doc_id=doc_id, new_status=new_status)
    return {"success": True, "doc_id": doc_id, "status": new_status.value}
