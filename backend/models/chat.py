"""
backend/models/chat.py
─────────────────────────────────────────────────────────────
Module 5 – Pydantic request/response models for the chat API.

Designed for forward compatibility:
  • Module 6 adds `use_rag: bool` and `document_ids: list`
  • Module 7 adds `agent_mode`, `session_id`, streaming flags
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from models.rag import DocumentChunk


# ── Request models ────────────────────────────────────────────

class ChatAttachment(BaseModel):
    """Direct transient attachment uploaded in AI Chat."""
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File extension/type (e.g. PDF, DOCX, TXT)")
    text: str = Field(..., description="Extracted text content from the file")
    page_count: Optional[int] = Field(default=1, description="Number of pages if applicable")


class ChatParseFileResponse(BaseModel):
    """Response model for POST /api/chat/parse-file."""
    filename: str
    file_type: str
    char_count: int
    page_count: int
    text: str


class ChatMessage(BaseModel):
    """A single message turn (for conversation history)."""
    role: str = Field(..., description="Either 'user' or 'model'")
    content: str = Field(..., min_length=1, description="Message content")


class ChatRequest(BaseModel):
    """
    POST /api/chat — request body.

    Module 5:  message + optional system_prompt override.
    Module 6+: use_rag, document_ids, session_id will be added here.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=32_000,
        description="The user's question or message",
        examples=["What is the leave policy?"],
    )
    system_prompt: Optional[str] = Field(
        default=None,
        max_length=4_000,
        description="Optional override for the system instruction",
    )
    conversation_history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Previous turns for multi-turn conversations (Module 7+)",
    )
    attachments: Optional[List[ChatAttachment]] = Field(
        default=None,
        description="Direct transient document attachments uploaded in AI Chat",
    )
    # Reserved for Module 6 (RAG) — accepted now, ignored in Module 5
    use_rag: bool = Field(
        default=False,
        description="Enable RAG retrieval (Module 6+, ignored in Module 5)",
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Restrict retrieval to specific documents (Module 6+)",
    )

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty or whitespace only")
        return v


# ── Response models ───────────────────────────────────────────

class ChatResponse(BaseModel):
    """POST /api/chat — success response."""
    message: str           = Field(..., description="Echo of the user's message")
    response: str          = Field(..., description="Gemini-generated reply")
    model: str             = Field(..., description="Gemini model used")
    status: str            = Field(default="success")
    timestamp: str         = Field(..., description="UTC ISO-8601 timestamp")
    processing_time: float = Field(..., description="Total server-side latency in seconds")
    retrieval_time: float  = Field(default=0.0, description="Time spent on RAG retrieval (Module 6+)")
    prompt_tokens: Optional[int]     = Field(default=None)
    completion_tokens: Optional[int] = Field(default=None)
    finish_reason: Optional[str]     = Field(default=None)
    sources_used: Optional[int]      = Field(default=None, description="Number of RAG chunks used")
    citations: List                  = Field(default_factory=list, description="Source chunks used in the answer (Module 6+)")


class ChatErrorResponse(BaseModel):
    """Error response shape — consistent across all 4xx / 5xx errors."""
    status: str    = Field(default="error")
    error: str     = Field(..., description="Human-readable error description")
    detail: Optional[str] = Field(default=None, description="Technical details")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class LLMHealthResponse(BaseModel):
    """GET /api/chat/health response."""
    status: str             = Field(..., description="'healthy' or 'unhealthy'")
    model: str              = Field(..., description="Gemini model identifier")
    latency_ms: Optional[int] = Field(default=None)
    response: Optional[str]   = Field(default=None, description="Sample model output")
    error: Optional[str]      = Field(default=None)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
