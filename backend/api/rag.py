"""
backend/api/rag.py
─────────────────────────────────────────────────────────────
Module 6 – RAG REST API Router

Endpoints:
  POST /api/rag/chat    → RAG-augmented Gemini answer with citations
  POST /api/rag/search  → Retrieve chunks only (debug / evaluation)
  GET  /api/rag/health  → FAISS + embedder + LLM combined health

Architecture note:
  • This router is independent of /api/chat — it owns the full
    RAG pipeline (retrieve → build prompt → generate → return citations)
  • /api/chat with use_rag=true delegates here (via retriever_service)
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from models.rag import (
    RAGChatRequest,
    RAGChatResponse,
    SearchRequest,
    SearchResponse,
    RAGHealthResponse,
    RAGComponentHealth,
    DocumentChunk,
)
from services.retriever_service import get_retriever_service
from services.prompt_builder import get_prompt_builder
from services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG – Module 6"])


# ─────────────────────────────────────────────────────────────
# POST /api/rag/chat
# ─────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=RAGChatResponse,
    summary="RAG-augmented chat — answer grounded in uploaded documents",
    description=(
        "**Module 6** — Full RAG pipeline:\n\n"
        "1. Embed the user's query (Gemini `retrieval_query` task)\n"
        "2. Search FAISS for top-k similar document chunks\n"
        "3. Filter by similarity threshold\n"
        "4. Build a contextual prompt with `[Source N]` citations\n"
        "5. Generate an answer with Gemini Flash\n"
        "6. Return the answer with full citation metadata\n\n"
        "Set `similarity_threshold=0.0` and `top_k=10` for maximum recall."
    ),
)
async def rag_chat(request: RAGChatRequest) -> RAGChatResponse:
    total_start = time.perf_counter()
    logger.info(
        "RAG chat: query=%r | top_k=%d | threshold=%.2f | doc_filter=%s",
        request.message[:80], request.top_k, request.similarity_threshold,
        request.document_ids or "all",
    )

    # ── Step 1 & 2 & 3: Retrieve ──────────────────────────────
    try:
        retriever = get_retriever_service()
        retrieval = await retriever.retrieve(
            query=request.message,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            document_ids=request.document_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval error: {exc}",
        )

    # ── Step 4: Build prompt ──────────────────────────────────
    builder = get_prompt_builder()
    context_str, system_prompt = builder.build(
        chunks=retrieval.chunks,
        query=request.message,
    )

    if retrieval.chunks:
        logger.debug("Retrieved chunks:\n%s", builder.build_search_summary(retrieval.chunks))

    # Override system prompt if caller provided one
    effective_system_prompt = request.system_prompt or system_prompt

    # ── Step 5: Generate with Gemini ──────────────────────────
    gen_start = time.perf_counter()
    try:
        llm = get_llm_service()
        llm_result = await llm.generate(
            user_prompt=request.message,
            context=context_str if context_str else None,
            system_prompt=effective_system_prompt,
            conversation_history=_format_history(request.conversation_history),
            attachments=request.attachments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Gemini timed out: {exc}",
        )
    except RuntimeError as exc:
        err = str(exc).lower()
        if "429" in err or "quota" in err or "rate limit" in err:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Gemini rate limit reached. Please retry in a moment.",
            )
        logger.exception("LLM generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM error: {exc}",
        )

    generation_time = round(time.perf_counter() - gen_start, 3)
    total_time = round(time.perf_counter() - total_start, 3)

    # ── Step 6: Build citations ───────────────────────────────
    citations = _build_citations(retrieval.chunks)

    logger.info(
        "RAG complete: total=%.2fs | retrieval=%.2fs | generation=%.2fs | "
        "chunks=%d | fallback=%s",
        total_time, retrieval.retrieval_time, generation_time,
        len(retrieval.chunks), retrieval.used_fallback,
    )

    return RAGChatResponse(
        query=request.message,
        answer=llm_result.content,
        model=llm_result.model,
        status="success",
        timestamp=llm_result.timestamp,
        processing_time=total_time,
        retrieval_time=retrieval.retrieval_time,
        generation_time=generation_time,
        chunks_retrieved=len(retrieval.chunks),
        chunks_found=retrieval.total_found,
        citations=citations,
        prompt_tokens=llm_result.prompt_tokens,
        completion_tokens=llm_result.completion_tokens,
        finish_reason=llm_result.finish_reason,
        used_fallback=retrieval.used_fallback,
    )


# ─────────────────────────────────────────────────────────────
# POST /api/rag/search
# ─────────────────────────────────────────────────────────────

@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Retrieve document chunks — debug and evaluation endpoint",
    description=(
        "Returns the raw FAISS search results for a query **without** calling Gemini. "
        "Use this to:\n"
        "- Inspect which chunks would be retrieved for a given query\n"
        "- Tune `similarity_threshold` and `top_k` parameters\n"
        "- Evaluate retrieval quality before testing full RAG\n\n"
        "Set `similarity_threshold=0.0` to see all top results regardless of score."
    ),
)
async def rag_search(request: SearchRequest) -> SearchResponse:
    logger.info(
        "RAG search: query=%r | top_k=%d | threshold=%.2f",
        request.query[:80], request.top_k, request.similarity_threshold,
    )

    try:
        retriever = get_retriever_service()
        retrieval = await retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            document_ids=request.document_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Search failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search error: {exc}",
        )

    chunks = _build_citations(retrieval.chunks)

    return SearchResponse(
        query=request.query,
        chunks=chunks,
        total_found=retrieval.total_found,
        retrieval_time=retrieval.retrieval_time,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ─────────────────────────────────────────────────────────────
# GET /api/rag/health
# ─────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=RAGHealthResponse,
    summary="RAG system health — FAISS + embedder + Gemini",
)
async def rag_health() -> RAGHealthResponse:
    """Check all three RAG components and return combined health status."""
    components: list[RAGComponentHealth] = []
    index_vectors = None
    index_documents = None

    # ── Check: Retriever (embedder + vector store) ─────────────
    try:
        retriever = get_retriever_service()
        retriever_health = await retriever.health_check()

        emb = retriever_health.get("embedder", {})
        components.append(RAGComponentHealth(
            name="embedder",
            status=emb.get("status", "unhealthy"),
            detail=emb.get("model") or emb.get("error"),
            latency_ms=emb.get("latency_ms"),
        ))

        vs = retriever_health.get("vector_store", {})
        components.append(RAGComponentHealth(
            name="faiss_index",
            status=vs.get("status", "unhealthy"),
            detail=vs.get("error"),
        ))
        if vs.get("status") == "healthy":
            index_vectors = vs.get("vectors")
            index_documents = vs.get("documents")

    except Exception as exc:
        components.append(RAGComponentHealth(name="retriever", status="unhealthy", detail=str(exc)))

    # ── Check: LLM (Gemini) ────────────────────────────────────
    try:
        llm = get_llm_service()
        llm_health = await llm.health_check()
        components.append(RAGComponentHealth(
            name="gemini_llm",
            status=llm_health.get("status", "unhealthy"),
            detail=llm_health.get("model") or llm_health.get("error"),
            latency_ms=llm_health.get("latency_ms"),
        ))
    except Exception as exc:
        components.append(RAGComponentHealth(name="gemini_llm", status="unhealthy", detail=str(exc)))

    # ── Overall status ─────────────────────────────────────────
    statuses = {c.status for c in components}
    if all(c.status == "healthy" for c in components):
        overall = "healthy"
    elif "healthy" in statuses:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return RAGHealthResponse(
        overall_status=overall,
        components=components,
        index_vectors=index_vectors,
        index_documents=index_documents,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _build_citations(chunks) -> list[DocumentChunk]:
    """Convert SearchResult list → DocumentChunk list (1-based source index)."""
    return [
        DocumentChunk(
            source_index=i,
            document_id=chunk.document_id,
            file_name=chunk.file_name,
            category=chunk.category,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            similarity=round(chunk.score, 4),
            text_preview=chunk.chunk_text[:300].strip(),
            full_text=chunk.chunk_text,
        )
        for i, chunk in enumerate(chunks, 1)
    ]


def _format_history(history: list | None) -> list:
    """Convert conversation_history dicts to Gemini SDK format."""
    if not history:
        return []
    formatted = []
    for turn in history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role and content:
            formatted.append({"role": role, "parts": [content]})
    return formatted
