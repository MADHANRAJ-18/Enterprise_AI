"""
backend/models/processing.py
─────────────────────────────────────────────────────────────
Pydantic models for the Module 4 processing pipeline API.
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


# ── Processing request / response ────────────────────────────

class ProcessRequest(BaseModel):
    """Request body for POST /api/processing/process-all."""
    user_id: str = Field(..., description="Authenticated user UUID")
    force_reindex: bool = Field(
        False,
        description="If True, re-processes already-indexed documents",
    )


class ProcessingStatusEnum:
    QUEUED     = "queued"
    PROCESSING = "processing"
    INDEXED    = "indexed"
    FAILED     = "failed"
    SKIPPED    = "skipped"


class DocumentProcessingResult(BaseModel):
    """Result for a single document's processing run."""
    document_id: str
    file_name: str
    status: str                         # indexed | failed | skipped
    chunks_created: int = 0
    vectors_added: int = 0
    error: Optional[str] = None
    processing_time_seconds: Optional[float] = None


class ProcessAllResponse(BaseModel):
    """Response for POST /api/processing/process-all."""
    success: bool
    total_documents: int
    indexed: int
    failed: int
    skipped: int
    results: List[DocumentProcessingResult]
    total_time_seconds: float


class ProcessSingleResponse(BaseModel):
    """Response for POST /api/processing/process/{doc_id}."""
    success: bool
    result: DocumentProcessingResult
    message: str


# ── Chunk metadata ────────────────────────────────────────────

class ChunkMetadata(BaseModel):
    """Metadata for a single indexed chunk (returned by status endpoints)."""
    id: Optional[str] = None
    document_id: str
    user_id: str
    chunk_index: int
    chunk_text: str
    page_number: Optional[int] = None
    token_count: Optional[int] = None
    category: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Status / stats ────────────────────────────────────────────

class DocumentIndexingStatus(BaseModel):
    """Indexing status for a single document."""
    document_id: str
    file_name: str
    status: str
    chunks_in_db: int
    vectors_in_faiss: bool
    uploaded_at: Optional[datetime] = None


class IndexingStatsResponse(BaseModel):
    """Response for GET /api/processing/status."""
    user_id: str
    total_documents: int
    indexed_count: int
    processing_count: int
    failed_count: int
    uploaded_count: int       # Documents waiting to be processed
    total_chunks: int
    total_vectors_in_faiss: int
    documents: List[DocumentIndexingStatus]


class IndexHealthResponse(BaseModel):
    """Response for GET /api/processing/health."""
    embedder_ready: bool
    faiss_ready: bool
    faiss_total_vectors: int
    faiss_total_documents: int
    embedding_model: str
    embedding_dimension: int


# ── Search (Module 5 preview) ─────────────────────────────────

class SearchRequest(BaseModel):
    """Request body for semantic search (used in Module 5)."""
    query: str = Field(..., min_length=1, max_length=2000)
    user_id: str
    k: int = Field(5, ge=1, le=20, description="Number of results to return")
    filter_document_id: Optional[str] = None
    filter_category: Optional[str] = None


class SearchResultItem(BaseModel):
    """A single chunk result from semantic search."""
    score: float
    document_id: str
    chunk_index: int
    chunk_text: str
    file_name: str
    category: str
    page_number: Optional[int] = None


class SearchResponse(BaseModel):
    """Response for semantic search."""
    query: str
    results: List[SearchResultItem]
    total_results: int


# ── Delete index response ─────────────────────────────────────

class DeleteIndexResponse(BaseModel):
    """Response for DELETE /api/processing/index/{doc_id}."""
    success: bool
    document_id: str
    vectors_removed: int
    chunks_removed: int
    message: str
