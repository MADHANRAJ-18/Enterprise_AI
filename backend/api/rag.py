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

from services.citation_service import optimize_citations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG – Module 6"])

GREETING_RESPONSES = {
    "hi": "Hello! How can I assist you with your company documents and knowledge base today?",
    "hello": "Hello! How can I help you today? Feel free to ask about company policies, documents, or tasks.",
    "hey": "Hey there! How can I assist you today?",
    "heya": "Hello! How can I help you today?",
    "hi there": "Hello! What can I help you find today?",
    "hello there": "Hello! How can I assist you today?",
    "good morning": "Good morning! How can I help you today?",
    "good afternoon": "Good afternoon! How can I help you today?",
    "good evening": "Good evening! How can I help you today?",
    "howdy": "Howdy! How can I assist you today?",
    "thanks": "You're very welcome! Let me know if you need anything else.",
    "thank you": "You're welcome! Feel free to ask if you have more questions.",
    "who are you": "I am your Enterprise AI Knowledge Assistant. I help you search, summarize, and understand uploaded company documents and policies.",
    "what can you do": "I can answer questions based on your company documents, summarize reports, compare policies, perform gap analysis, and provide precise citations.",
    "help": "You can ask me questions about your uploaded documents, search company policies, request summaries, or ask for document comparisons. How can I help?",
}

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

    scope = request.scope or "company"

    norm_q = request.message.strip().lower().strip("!?.,")
    if norm_q in GREETING_RESPONSES and not request.attachments and not request.document_ids:
        fast_answer = GREETING_RESPONSES[norm_q]
        elapsed = round(time.perf_counter() - total_start, 3)
        return RAGChatResponse(
            query=request.message,
            answer=fast_answer,
            model="Enterprise AI (Fast Greeting)",
            status="success",
            timestamp=datetime.now(timezone.utc).isoformat(),
            processing_time=elapsed,
            retrieval_time=0.0,
            generation_time=elapsed,
            chunks_retrieved=0,
            chunks_found=0,
            citations=[],
            prompt_tokens=len(request.message),
            completion_tokens=len(fast_answer.split()),
            finish_reason="stop",
            retrieval_scope=scope,
            used_fallback=False,
        )

    logger.info(

        "RAG chat: query=%r | scope=%s | top_k=%d | threshold=%.2f | doc_filter=%s",

        request.message[:80], scope, request.top_k, request.similarity_threshold,

        request.document_ids or "all",

    )

    try:
        retriever = get_retriever_service()

        retrieval = await retriever.retrieve(

            query=request.message,

            top_k=request.top_k,

            similarity_threshold=request.similarity_threshold,

            document_ids=request.document_ids,

            scope=scope,

            user_id=request.user_id,

            company_id=request.company_id,

        )

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    except RuntimeError as exc:
        logger.error("Retrieval failed: %s", exc)

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Retrieval error: {exc}",

        )

    builder = get_prompt_builder()

    context_str, system_prompt = builder.build(

        chunks=retrieval.chunks,

        query=request.message,

    )

    if retrieval.chunks:
        logger.debug("Retrieved chunks:\n%s", builder.build_search_summary(retrieval.chunks))

    effective_system_prompt = request.system_prompt or system_prompt

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

    citations = optimize_citations(
        answer_text=llm_result.content,
        chunks=retrieval.chunks,
        min_similarity=request.similarity_threshold or 0.25,
    )

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

        retrieval_scope=retrieval.retrieval_scope,

    )

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
    scope = request.scope or "company"

    logger.info(

        "RAG search: query=%r | scope=%s | top_k=%d | threshold=%.2f",

        request.query[:80], scope, request.top_k, request.similarity_threshold,

    )

    try:
        retriever = get_retriever_service()

        retrieval = await retriever.retrieve(

            query=request.query,

            top_k=request.top_k,

            similarity_threshold=request.similarity_threshold,

            document_ids=request.document_ids,

            scope=scope,

            user_id=request.user_id,

            company_id=request.company_id,

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

        retrieval_scope=retrieval.retrieval_scope,

        timestamp=datetime.now(timezone.utc).isoformat(),

    )

@router.get(

    "/health",

    response_model=RAGHealthResponse,

    summary="RAG system health — FAISS + embedder + Gemini",

)

async def rag_health() -> RAGHealthResponse:
    components: list[RAGComponentHealth] = []

    index_vectors = None

    index_documents = None

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

def _build_citations(chunks) -> list[DocumentChunk]:
    return [

        DocumentChunk(

            source_index=i,

            document_id=chunk.document_id,

            chunk_id=chunk.chunk_id,

            file_name=chunk.file_name,

            category=chunk.category,

            chunk_index=chunk.chunk_index,

            page_number=chunk.page_number,

            similarity=round(chunk.score, 4),

            text_preview=chunk.chunk_text[:300].strip(),

            full_text=chunk.chunk_text,

            scope=chunk.scope,

            user_id=chunk.user_id,

        )

        for i, chunk in enumerate(chunks, 1)

    ]

def _format_history(history: list | None) -> list:
    if not history:
        return []

    formatted = []

    for turn in history:
        role = turn.get("role", "user")

        content = turn.get("content", "")

        if role and content:
            formatted.append({"role": role, "parts": [content]})

    return formatted
