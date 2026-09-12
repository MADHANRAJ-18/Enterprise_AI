from __future__ import annotations

from datetime import datetime, timezone

from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

class EvidenceSpan(BaseModel):
    text:  str            = Field(..., description="Exact grounding excerpt text")
    score: Optional[float] = Field(default=None, description="Relevance score to answer")

class DocumentChunk(BaseModel):
    source_index:   int                   = Field(..., description="Citation index (1-based) used in the answer")
    document_id:    str                   = Field(..., description="Supabase document UUID")
    chunk_id:       str                   = Field(default="", description="Unique chunk identifier: '{doc_id}::chunk_{index}'")
    file_name:      str                   = Field(..., description="Original uploaded filename")
    category:       str                   = Field(default="", description="Document category")
    chunk_index:    int                   = Field(..., description="0-based position of chunk within document")
    page_number:    Optional[int]         = Field(default=None, description="Page number if extracted")
    similarity:     float                 = Field(..., description="Cosine similarity score (0–1)")
    text_preview:   str                   = Field(..., description="First 300 chars of the chunk text")
    full_text:      str                   = Field(..., description="Full chunk text used in the prompt")
    source_text:    Optional[str]         = Field(default=None, description="Exact grounding excerpt used in answer")
    evidence_spans: List[EvidenceSpan]    = Field(default_factory=list, description="All exact evidence spans supporting the answer")
    scope:          str                   = Field(default="company", description="'company' | 'workspace'")
    user_id:        Optional[str]         = Field(default=None, description="Set for workspace-scoped chunks")

class RAGChatRequest(BaseModel):
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

    scope: str = Field(

        default="company",

        description=(

            "Retrieval scope: 'company' (shared knowledge), "

            "'workspace' (private employee docs), or 'both'. "

            "Defaults to 'company'. Future LangGraph Coordinator sets this automatically."

        ),

    )

    user_id: Optional[str] = Field(

        default=None,

        description="User UUID — required when scope includes 'workspace'",

    )

    company_id: Optional[str] = Field(

        default=None,

        description="Company UUID — required for company-scoped retrieval",

    )

    @field_validator("message")

    @classmethod

    def strip_message(cls, v: str) -> str:
        v = v.strip()

        if not v:
            raise ValueError("message cannot be empty or whitespace only")

        return v

    @field_validator("scope")

    @classmethod

    def validate_scope(cls, v: str) -> str:
        valid = {"company", "workspace", "both"}

        if v not in valid:
            raise ValueError(f"scope must be one of {valid}")

        return v

class RAGChatResponse(BaseModel):
    query:          str   = Field(..., description="The original user question")

    answer:         str   = Field(..., description="LLM-generated answer grounded in documents")

    model:          str   = Field(..., description="LLM model used for generation")

    status:         str   = Field(default="success")

    timestamp:      str   = Field(..., description="UTC ISO-8601 timestamp")

    processing_time:  float = Field(..., description="Total wall-clock time in seconds")

    retrieval_time:   float = Field(..., description="Time spent on FAISS search + embedding in seconds")

    generation_time:  float = Field(..., description="Time spent on LLM generation in seconds")

    chunks_retrieved:  int              = Field(..., description="Number of chunks passed to LLM")

    chunks_found:      int              = Field(..., description="Total chunks above the threshold before top-k")

    citations:         List[DocumentChunk] = Field(default_factory=list, description="Source chunks used in the answer")

    prompt_tokens:     Optional[int] = Field(default=None)

    completion_tokens: Optional[int] = Field(default=None)

    finish_reason:     Optional[str] = Field(default=None)

    retrieval_scope: str = Field(default="company", description="Scope used for retrieval")

    used_fallback: bool = Field(

        default=False,

        description="True when no chunks passed the threshold; LLM answered from general knowledge",

    )

class SearchRequest(BaseModel):
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

    scope: str = Field(

        default="company",

        description="'company' | 'workspace' | 'both'",

    )

    user_id: Optional[str] = Field(default=None)

    company_id: Optional[str] = Field(default=None)

    @field_validator("query")

    @classmethod

    def strip_query(cls, v: str) -> str:
        return v.strip()

class SearchResponse(BaseModel):
    query:           str               = Field(..., description="Echo of the search query")

    chunks:          List[DocumentChunk] = Field(..., description="Retrieved chunks ordered by similarity")

    total_found:     int               = Field(..., description="Total chunks above threshold")

    retrieval_time:  float             = Field(..., description="Seconds spent on search")

    retrieval_scope: str               = Field(default="company")

    timestamp:       str = Field(

        default_factory=lambda: datetime.now(timezone.utc).isoformat()

    )

class RAGComponentHealth(BaseModel):
    name:       str           = Field(..., description="Component name")

    status:     str           = Field(..., description="'healthy' | 'unhealthy' | 'degraded'")

    detail:     Optional[str] = Field(default=None)

    latency_ms: Optional[int] = Field(default=None)

class RAGHealthResponse(BaseModel):
    overall_status:   str                      = Field(..., description="'healthy' | 'degraded' | 'unhealthy'")

    components:       List[RAGComponentHealth] = Field(..., description="Per-component status")

    index_vectors:    Optional[int]            = Field(default=None, description="Vectors in FAISS index")

    index_documents:  Optional[int]            = Field(default=None, description="Documents in FAISS index")

    timestamp: str = Field(

        default_factory=lambda: datetime.now(timezone.utc).isoformat()

    )
