"""
backend/models/rag.py
─────────────────────────────────────────────────────────────
Module 6 – Pydantic request/response models for the RAG API.

Endpoints:
  POST /api/rag/chat    → RAG-augmented chat with citations
  POST /api/rag/search  → Debug: raw chunk retrieval + scores
  GET  /api/rag/health  → Combined FAISS + embedder + LLM health

Forward compatible with Module 7 (LangGraph):
  • agent_mode, session_id, streaming flags added there
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


# ── Shared: Retrieved chunk ───────────────────────────────────

class DocumentChunk(BaseModel):
    """A single retrieved document chunk with retrieval metadata."""
    source_index:  int            = Field(..., description="Citation index (1-based) used in the answer")
    document_id:   str            = Field(..., description="Supabase document UUID")
    file_name:     str            = Field(..., description="Original uploaded filename")
    category:      str            = Field(default="", description="Document category")
    chunk_index:   int            = Field(..., description="0-based position of chunk within document")
    page_number:   Optional[int]  = Field(default=None, description="Page number if extracted")
    similarity:    float          = Field(..., description="Cosine similarity score (0–1)")
    text_preview:  str            = Field(..., description="First 300 chars of the chunk text")
    full_text:     str            = Field(..., description="Full chunk text used in the prompt")


# ── RAG Chat ──────────────────────────────────────────────────

class RAGChatRequest(BaseModel):
    """
    POST /api/rag/chat — request body.

    Module 6: RAG-augmented generation.
    Module 7: session_id + agent_mode will be added here.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=32_000,
        description="The user's question or message",
        examples=["What is the employee leave policy?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of chunks to retrieve from FAISS",
    )
    similarity_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score to include a chunk (0–1)",
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Restrict retrieval to specific document UUIDs (null = all documents)",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        max_length=4_000,
        description="Override the default system instruction sent to Gemini",
    )
    conversation_history: Optional[List[dict]] = Field(
        default=None,
        description="Previous turns [{role, content}] for multi-turn chat (Module 7+)",
    )
    attachments: Optional[List[dict]] = Field(
        default=None,
        description="Direct transient document attachments uploaded in AI Chat",
    )

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty or whitespace only")
        return v


class RAGChatResponse(BaseModel):
    """POST /api/rag/chat — success response."""
    # Core
    query:          str   = Field(..., description="The original user question")
    answer:         str   = Field(..., description="Gemini-generated answer grounded in documents")
    model:          str   = Field(..., description="Gemini model used for generation")
    status:         str   = Field(default="success")
    timestamp:      str   = Field(..., description="UTC ISO-8601 timestamp")

    # Timing
    processing_time:  float = Field(..., description="Total wall-clock time in seconds")
    retrieval_time:   float = Field(..., description="Time spent on FAISS search + embedding in seconds")
    generation_time:  float = Field(..., description="Time spent on Gemini generation in seconds")

    # Retrieval metadata
    chunks_retrieved:  int              = Field(..., description="Number of chunks passed to Gemini")
    chunks_found:      int              = Field(..., description="Total chunks above the threshold before top-k")
    citations:         List[DocumentChunk] = Field(default_factory=list, description="Source chunks used in the answer")

    # Token usage
    prompt_tokens:     Optional[int] = Field(default=None)
    completion_tokens: Optional[int] = Field(default=None)
    finish_reason:     Optional[str] = Field(default=None)

    # Fallback flag (no relevant docs found)
    used_fallback: bool = Field(
        default=False,
        description="True when no chunks passed the threshold; Gemini answered from general knowledge",
    )


# ── RAG Search (debug / evaluation) ──────────────────────────

class SearchRequest(BaseModel):
    """POST /api/rag/search — retrieve chunks without generating an answer."""
    query: str = Field(..., min_length=1, max_length=8_000, description="Search query")
    top_k: int = Field(default=10, ge=1, le=50, description="Max chunks to return")
    similarity_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Min similarity score (0 = return all top_k results)",
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Restrict to specific document UUIDs",
    )

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()


class SearchResponse(BaseModel):
    """POST /api/rag/search — response."""
    query:          str               = Field(..., description="Echo of the search query")
    chunks:         List[DocumentChunk] = Field(..., description="Retrieved chunks ordered by similarity")
    total_found:    int               = Field(..., description="Total chunks above threshold")
    retrieval_time: float             = Field(..., description="Seconds spent on search")
    timestamp:      str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── RAG Health ────────────────────────────────────────────────

class RAGComponentHealth(BaseModel):
    """Health status of a single RAG component."""
    name:       str           = Field(..., description="Component name")
    status:     str           = Field(..., description="'healthy' | 'unhealthy' | 'degraded'")
    detail:     Optional[str] = Field(default=None)
    latency_ms: Optional[int] = Field(default=None)


class RAGHealthResponse(BaseModel):
    """GET /api/rag/health — combined health of all RAG components."""
    overall_status: str                        = Field(..., description="'healthy' | 'degraded' | 'unhealthy'")
    components:     List[RAGComponentHealth]   = Field(..., description="Per-component status")
    index_vectors:  Optional[int]              = Field(default=None, description="Vectors in FAISS index")
    index_documents: Optional[int]             = Field(default=None, description="Documents in FAISS index")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
