from __future__ import annotations

from datetime import datetime, timezone

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

class AgentCitation(BaseModel):
    source_index:   int                         = Field(..., description="1-based citation index")
    document_id:    str                         = Field(..., description="Supabase document UUID")
    file_name:      str                         = Field(..., description="Original uploaded filename")
    page:           Optional[int]               = Field(default=None, description="Page number if available")
    page_number:    Optional[int]               = Field(default=None, description="Page number if available")
    chunk_id:       str                         = Field(..., description="Unique chunk identifier")
    scope:          str                         = Field(default="company", description="'company' | 'workspace'")
    score:          float                       = Field(..., description="Cosine similarity score (0–1)")
    full_text:      Optional[str]               = Field(default=None, description="Full chunk text excerpt")
    text_preview:   Optional[str]               = Field(default=None, description="Chunk text preview")
    source_text:    Optional[str]               = Field(default=None, description="Focused grounding excerpt for PDF highlight")
    evidence_spans: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="All exact evidence spans supporting the answer")

class AgentChatRequest(BaseModel):
    message: str = Field(

        ...,

        min_length=1,

        max_length=32_000,

        description="The user's question or instruction",

        examples=["What is the company's leave policy?"],

    )

    user_id: str = Field(

        ...,

        description="Authenticated user UUID — required for workspace security enforcement",

    )

    company_id: str = Field(

        ...,

        description="User's company UUID — used for company-scope retrieval",

    )

    conversation_id: Optional[str] = Field(

        default=None,

        description="Active conversation UUID. If provided, prior messages are loaded for follow-up context.",

    )

    scope: Optional[str] = Field(

        default=None,

        description=(

            "Initial retrieval scope hint: 'company' | 'workspace' | 'both'. "

            "The Coordinator agent will override this based on query analysis. "

            "Leave null to let the Coordinator decide automatically."

        ),

    )

    top_k: int = Field(

        default=5,

        ge=1,

        le=20,

        description="Maximum chunks to retrieve per scope from FAISS",

    )

    similarity_threshold: float = Field(

        default=0.3,

        ge=0.0,

        le=1.0,

        description="Minimum cosine similarity score to include a chunk",

    )

    conversation_history: Optional[List[Dict[str, str]]] = Field(

        default=None,

        description=(

            "Explicit conversation history [{role, content}]. "

            "If omitted and conversation_id is set, history is loaded from the database."

        ),

    )

    @field_validator("message")

    @classmethod

    def strip_message(cls, v: str) -> str:
        v = v.strip()

        if not v:
            raise ValueError("message cannot be empty")

        return v

    @field_validator("scope")

    @classmethod

    def validate_scope(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v

        valid = {"company", "workspace", "both"}

        if v not in valid:
            raise ValueError(f"scope must be one of {valid} or null")

        return v

class AgentChatResponse(BaseModel):
    query:        str = Field(..., description="The original user question")

    final_answer: str = Field(..., description="LangGraph-orchestrated final answer")

    status:       str = Field(default="success")

    timestamp:    str = Field(

        default_factory=lambda: datetime.now(timezone.utc).isoformat()

    )

    intent:          str             = Field(..., description="Detected intent: question_answering | summarization | comparison | gap_analysis")

    retrieval_scope: str             = Field(..., description="Scope used: company | workspace | both")

    workflow_path:   List[str]       = Field(default_factory=list, description="Ordered list of nodes that executed")

    citations:         List[AgentCitation] = Field(default_factory=list, description="Document citations used in the answer")

    chunks_retrieved:  int                 = Field(default=0, description="Total chunks retrieved")

    summaries:         List[str]       = Field(default_factory=list, description="Per-summarizer results (up to 3)")

    comparison_result: Optional[str]   = Field(default=None, description="Comparison/gap analysis structured output")

    gap_analysis:      Optional[str]   = Field(default=None, description="Gap analysis result (alias for gap_analysis intent)")

    processing_time: float = Field(..., description="Total wall-clock time in seconds")

    model: str = Field(default="gemini-2.5-flash", description="LLM model used")

    errors: List[str] = Field(default_factory=list, description="Non-fatal warnings/errors encountered during workflow")

    conversation_id: Optional[str] = Field(default=None, description="Conversation UUID if messages were persisted")

class AgentHealthResponse(BaseModel):
    overall_status: str              = Field(..., description="'healthy' | 'degraded' | 'unhealthy'")

    workflow_ready: bool             = Field(..., description="LangGraph workflow compiled successfully")

    components:     List[Dict[str, Any]] = Field(default_factory=list)

    timestamp:      str = Field(

        default_factory=lambda: datetime.now(timezone.utc).isoformat()

    )
