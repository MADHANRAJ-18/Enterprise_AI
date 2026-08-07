"""
backend/api/chat.py
─────────────────────────────────────────────────────────────
Module 5 / 6 – Chat REST API Router (Groq / Llama 3.3 70B)

Endpoints:
  POST /api/chat            →  generate a Groq (Llama 3.3 70B) response
  GET  /api/chat/health     →  verify Groq API connectivity
  GET  /api/chat/config     →  expose non-sensitive LLM config
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, UploadFile, File

from models.chat import (
    ChatRequest,
    ChatResponse,
    ChatErrorResponse,
    LLMHealthResponse,
    ChatParseFileResponse,
)
from models.rag import DocumentChunk
from services.llm_service import get_llm_service
from services.prompt_builder import get_prompt_builder
from processing.loaders import load_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat – Module 5/6"])


# ── POST /api/chat/parse-file ─────────────────────────────────

@router.post(
    "/parse-file",
    response_model=ChatParseFileResponse,
    summary="Extract text transiently from a file uploaded directly in AI Chat",
    description="Extract text from PDF, DOCX, TXT, CSV, or MD without persisting to database or vector store.",
)
async def parse_chat_file(file: UploadFile = File(...)) -> ChatParseFileResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    ext = os.path.splitext(file.filename)[1].lstrip(".").upper()
    if not ext:
        ext = "TXT"

    if ext in ("PDF", "DOCX"):
        file_type_loader = ext
    else:
        file_type_loader = "TXT"

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        doc = load_document(content, file_type_loader)
        return ChatParseFileResponse(
            filename=file.filename,
            file_type=ext,
            char_count=len(doc.full_text),
            page_count=doc.page_count,
            text=doc.full_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to parse chat attachment: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {exc}")


# ── POST /api/chat ────────────────────────────────────────────

@router.post(
    "",
    response_model=ChatResponse,
    responses={
        400: {"model": ChatErrorResponse, "description": "Invalid request"},
        429: {"model": ChatErrorResponse, "description": "Rate limit hit"},
        500: {"model": ChatErrorResponse, "description": "LLM or server error"},
        503: {"model": ChatErrorResponse, "description": "Groq service unavailable"},
    },
    summary="Send a message and receive a Groq Llama 3.3 70B response",
    description=(
        "**Module 5** — Direct Groq LLM generation.\n\n"
        "Send `message` and get a response from **Llama 3.3 70B Versatile**.\n\n"
        "**Module 6** prepends retrieved document context when `use_rag=true`."
    ),
)
async def chat(request: ChatRequest) -> ChatResponse:
    num_atts = len(request.attachments) if request.attachments else 0
    logger.info("Chat request: %d chars | attachments=%d | use_rag=%s", len(request.message), num_atts, request.use_rag)

    # ── Module 6: RAG retrieval ────────────────────────────────
    context: str | None = None
    retrieval_time: float = 0.0
    citations: list[DocumentChunk] = []

    if request.use_rag:
        try:
            from services.retriever_service import get_retriever_service
            retriever = get_retriever_service()
            retrieval = await retriever.retrieve(
                query=request.message,
                top_k=5,
                similarity_threshold=0.3,
                document_ids=request.document_ids,
            )
            builder = get_prompt_builder()
            context, system_prompt_override = builder.build(
                chunks=retrieval.chunks,
                query=request.message,
            )
            retrieval_time = retrieval.retrieval_time
            citations = [
                DocumentChunk(
                    source_index=i,
                    document_id=c.document_id,
                    file_name=c.file_name,
                    category=c.category,
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    similarity=round(c.score, 4),
                    text_preview=c.chunk_text[:300].strip(),
                    full_text=c.chunk_text,
                )
                for i, c in enumerate(retrieval.chunks, 1)
            ]
            if not request.system_prompt:
                request.system_prompt = system_prompt_override  # type: ignore[assignment]
            logger.info(
                "RAG via /chat: retrieved %d chunks (fallback=%s)",
                len(retrieval.chunks), retrieval.used_fallback,
            )
        except Exception as exc:
            logger.warning(
                "RAG retrieval failed (falling back to direct LLM): %s", exc
            )
            context = None
    # ── end Module 6 ───────────────────────────────────────────

    # Format history turns for LLM service
    history = []
    if request.conversation_history:
        history = [
            {"role": turn.role, "parts": [turn.content]}
            for turn in request.conversation_history
        ]

    try:
        llm = get_llm_service()
        result = await llm.generate(
            user_prompt=request.message,
            context=context,
            system_prompt=request.system_prompt,
            conversation_history=history,
            attachments=request.attachments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Groq API timed out: {exc}",
        )
    except RuntimeError as exc:
        err_str = str(exc).lower()
        if "rate limit" in err_str or "quota" in err_str or "429" in err_str:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Groq API rate limit reached. Please wait and retry.",
            )
        if "api_key" in err_str or "authentication" in err_str or "403" in err_str:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Groq authentication failed. Check GROQ_API_KEY.",
            )
        logger.exception("Unexpected LLM error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM generation failed: {exc}",
        )

    return ChatResponse(
        message=request.message,
        response=result.content,
        model=result.model,
        status="success",
        timestamp=result.timestamp,
        processing_time=result.processing_time,
        retrieval_time=retrieval_time,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        finish_reason=result.finish_reason,
        sources_used=len(citations) if citations else None,
        citations=citations,
    )


# ── GET /api/chat/health ──────────────────────────────────────

@router.get(
    "/health",
    response_model=LLMHealthResponse,
    summary="Check Groq LLM connectivity",
)
async def chat_health() -> LLMHealthResponse:
    """Send a minimal ping to Groq and return latency + model info."""
    try:
        llm    = get_llm_service()
        result = await llm.health_check()
        return LLMHealthResponse(
            status=result.get("status", "unhealthy"),
            model=result.get("model", "unknown"),
            latency_ms=result.get("latency_ms"),
            response=result.get("response"),
            error=result.get("error"),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        logger.error("LLM health check failed: %s", exc)
        return LLMHealthResponse(
            status="unhealthy",
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            error=str(exc),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# ── GET /api/chat/config ──────────────────────────────────────

@router.get(
    "/config",
    summary="View current LLM configuration (non-sensitive)",
)
async def chat_config() -> dict:
    """Return current Groq model settings — no API key exposed."""
    return {
        "model":                os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        "provider":             "Groq",
        "temperature":          float(os.getenv("LLM_TEMPERATURE", "0.7")),
        "max_output_tokens":    int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "8192")),
        "timeout_seconds":      int(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
        "rag_enabled":          True,
        "rag_top_k":            int(os.getenv("RAG_TOP_K", "5")),
        "rag_threshold":        float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3")),
        "module":               6,
    }
