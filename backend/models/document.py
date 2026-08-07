"""
backend/models/document.py
─────────────────────────────────────────────────────────────
Pydantic models for the documents API.
These models define the shape of request/response bodies and
map 1-to-1 with the Supabase `documents` table schema.
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    """Processing lifecycle status for a document."""
    UPLOADED   = "Uploaded"
    PROCESSING = "Processing"
    INDEXED    = "Indexed"
    FAILED     = "Failed"


class DocumentCategory(str, Enum):
    """Allowed document categories."""
    GENERAL  = "General"
    HR       = "HR"
    FINANCE  = "Finance"
    LEGAL    = "Legal"
    IT       = "IT"
    POLICIES = "Policies"
    RESEARCH = "Research"


# ── Request models ────────────────────────────────────────────

class DocumentUploadRequest(BaseModel):
    """
    Metadata sent alongside the file in the upload request.
    The file itself is received as a multipart form field.
    """
    category: DocumentCategory = DocumentCategory.GENERAL
    user_id: str = Field(..., description="Authenticated user's UUID from Supabase Auth")


class DocumentStatusUpdate(BaseModel):
    """Used by the Module 4 processing pipeline to update status."""
    status: DocumentStatus
    # Module 4+: additional fields for processing metadata
    # chunks_count: Optional[int] = None
    # embedding_model: Optional[str] = None


# ── Response models ───────────────────────────────────────────

class DocumentResponse(BaseModel):
    """Full document metadata as returned by the API."""
    id: UUID
    user_id: UUID
    file_name: str
    file_type: str
    file_size: int
    storage_path: str
    category: str
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class UploadResponse(BaseModel):
    """Response returned after a successful document upload."""
    success: bool
    document: DocumentResponse
    message: str


class DeleteResponse(BaseModel):
    """Response returned after a successful document deletion."""
    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Standard error response shape."""
    success: bool = False
    error: str
    detail: Optional[str] = None
