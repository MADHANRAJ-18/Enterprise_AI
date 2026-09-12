from __future__ import annotations

from datetime import datetime

from typing import List, Optional, Dict, Any

from uuid import UUID

from pydantic import BaseModel, Field

class ProcessRequest(BaseModel):
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
    document_id: str

    file_name: str

    status: str

    chunks_created: int = 0

    vectors_added: int = 0

    error: Optional[str] = None

    processing_time_seconds: Optional[float] = None

class ProcessAllResponse(BaseModel):
    success: bool

    total_documents: int

    indexed: int

    failed: int

    skipped: int

    results: List[DocumentProcessingResult]

    total_time_seconds: float

class ProcessSingleResponse(BaseModel):
    success: bool

    result: DocumentProcessingResult

    message: str

class ChunkMetadata(BaseModel):
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

class DocumentIndexingStatus(BaseModel):
    document_id: str

    file_name: str

    status: str

    chunks_in_db: int

    vectors_in_faiss: bool

    uploaded_at: Optional[datetime] = None

class IndexingStatsResponse(BaseModel):
    user_id: str

    total_documents: int

    indexed_count: int

    processing_count: int

    failed_count: int

    uploaded_count: int

    total_chunks: int

    total_vectors_in_faiss: int

    documents: List[DocumentIndexingStatus]

class IndexHealthResponse(BaseModel):
    embedder_ready: bool

    faiss_ready: bool

    faiss_total_vectors: int

    faiss_total_documents: int

    embedding_model: str

    embedding_dimension: int

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)

    user_id: str

    k: int = Field(5, ge=1, le=20, description="Number of results to return")

    filter_document_id: Optional[str] = None

    filter_category: Optional[str] = None

class SearchResultItem(BaseModel):
    score: float

    document_id: str

    chunk_index: int

    chunk_text: str

    file_name: str

    category: str

    page_number: Optional[int] = None

class SearchResponse(BaseModel):
    query: str

    results: List[SearchResultItem]

    total_results: int

class DeleteIndexResponse(BaseModel):
    success: bool

    document_id: str

    vectors_removed: int

    chunks_removed: int

    message: str
