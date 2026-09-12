from __future__ import annotations

from datetime import datetime

from typing import Optional, List

from uuid import UUID

from enum import Enum

from pydantic import BaseModel, Field, field_validator

class DocumentStatus(str, Enum):
    UPLOADED   = "Uploaded"

    PROCESSING = "Processing"

    INDEXED    = "Indexed"

    FAILED     = "Failed"

class DocumentCategory(str, Enum):
    GENERAL  = "General"

    HR       = "HR"

    FINANCE  = "Finance"

    LEGAL    = "Legal"

    IT       = "IT"

    POLICIES = "Policies"

    RESEARCH = "Research"

class DocumentScope(str, Enum):
    COMPANY   = "company"

    WORKSPACE = "workspace"

class DocumentUploadRequest(BaseModel):
    category:   DocumentCategory = DocumentCategory.GENERAL

    user_id:    str = Field(..., description="Authenticated user's UUID from Supabase Auth")

    scope:      DocumentScope = DocumentScope.WORKSPACE

    company_id: Optional[str] = Field(

        default=None,

        description="Company UUID — resolved from user profile if not provided",

    )

class DocumentUpdateRequest(BaseModel):
    category:  Optional[DocumentCategory] = None

    file_name: Optional[str] = None

class DocumentStatusUpdate(BaseModel):
    status: DocumentStatus

class DocumentResponse(BaseModel):
    id:           UUID

    user_id:      UUID

    file_name:    str

    file_type:    str

    file_size:    int

    storage_path: str

    category:     str

    status:       str

    scope:        str = "company"

    company_id:   Optional[str] = None

    uploaded_at:  datetime

    model_config = {"from_attributes": True}

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]

    total:     int

    page:      int

    page_size: int

class UploadResponse(BaseModel):
    success:  bool

    document: DocumentResponse

    message:  str

class DeleteResponse(BaseModel):
    success: bool

    message: str

class ErrorResponse(BaseModel):
    success: bool = False

    error:   str

    detail:  Optional[str] = None
