from __future__ import annotations

import os

import time

import logging

from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from models.agent import AgentChatRequest, AgentChatResponse, AgentCitation, AgentHealthResponse

from schemas.agent_state import make_initial_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent – Module 7"])

@router.post(

    "/chat",

    response_model=AgentChatResponse,

    summary="LangGraph multi-agent orchestrated chat",

    description=(

        "**Module 7** — Full LangGraph multi-agent pipeline:\n\n"

        "1. **Coordinator**: classify intent and retrieval scope\n"

        "2. **Retrieval**: scope-aware FAISS search (company / workspace / both)\n"

        "3. **Summarizer** (conditional): 3 parallel Gemini summarizers\n"

        "4. **Comparison** (conditional): comparison or gap analysis\n"

        "5. **Citation**: extract and verify source metadata\n"

        "6. **Answer**: final Gemini generation with full context\n\n"

        "**Intents**: `question_answering` | `summarization` | `comparison` | `gap_analysis`\n\n"

        "**Scopes**: `company` | `workspace` | `both`\n\n"

        "Requires `user_id` and `company_id` for security enforcement."

    ),

)

async def agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    total_start = time.perf_counter()

    logger.info(

        "Agent chat: query=%r | user=%s | company=%s | conv=%s",

        request.message[:80],

        request.user_id[:8] + "…" if len(request.user_id) > 8 else request.user_id,

        request.company_id[:8] + "…" if len(request.company_id) > 8 else request.company_id,

        request.conversation_id or "new",

    )

    conversation_history = await _load_conversation_history(

        conversation_id=request.conversation_id,

        user_id=request.user_id,

        explicit_history=request.conversation_history,

    )

    initial_state = make_initial_state(

        user_id=request.user_id,

        company_id=request.company_id,

        user_query=request.message,

        conversation_id=request.conversation_id,

        retrieval_scope=request.scope or "company",

        conversation_history=conversation_history,

    )

    try:
        from graph.workflow import get_workflow

        workflow = get_workflow()

        final_state = await workflow.ainvoke(initial_state)

    except Exception as exc:
        logger.exception("LangGraph workflow failed")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Agent workflow failed: {exc}",

        )

    final_answer      = final_state.get("final_answer") or _FALLBACK_ANSWER

    intent            = final_state.get("intent", "question_answering")

    retrieval_scope   = final_state.get("retrieval_scope", "company")

    workflow_path     = final_state.get("workflow_path", [])

    summaries         = final_state.get("summaries", [])

    comparison_result = final_state.get("comparison_result")

    gap_analysis      = final_state.get("gap_analysis")

    errors            = final_state.get("errors", [])

    retrieved_chunks  = final_state.get("retrieved_chunks", [])

    raw_citations = final_state.get("citations", [])

    citations = [
        AgentCitation(
            source_index=c["source_index"],
            document_id=c["document_id"],
            file_name=c["file_name"],
            page=c.get("page") or c.get("page_number"),
            page_number=c.get("page_number") or c.get("page"),
            chunk_id=c["chunk_id"],
            scope=c.get("scope", "company"),
            score=c.get("score", 0.0),
            full_text=c.get("full_text"),
            text_preview=c.get("text_preview"),
            source_text=c.get("source_text"),
            evidence_spans=c.get("evidence_spans") or [],
        )
        for c in raw_citations
    ]

    conv_id = await _persist_messages(

        conversation_id=request.conversation_id,

        user_id=request.user_id,

        user_message=request.message,

        assistant_message=final_answer,

        citations=raw_citations,

    )

    processing_time = round(time.perf_counter() - total_start, 3)

    model_name = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    logger.info(

        "Agent complete: intent=%s | scope=%s | chunks=%d | path=%s | %.2fs",

        intent, retrieval_scope, len(retrieved_chunks),

        "→".join(workflow_path), processing_time,

    )

    return AgentChatResponse(

        query=request.message,

        final_answer=final_answer,

        status="success" if not errors or final_answer != _FALLBACK_ANSWER else "partial",

        intent=intent,

        retrieval_scope=retrieval_scope,

        workflow_path=workflow_path,

        citations=citations,

        chunks_retrieved=len(retrieved_chunks),

        summaries=summaries,

        comparison_result=comparison_result,

        gap_analysis=gap_analysis,

        processing_time=processing_time,

        model=model_name,

        errors=errors,

        conversation_id=conv_id,

    )

@router.get(

    "/health",

    response_model=AgentHealthResponse,

    summary="LangGraph agent system health",

)

async def agent_health() -> AgentHealthResponse:
    components = []

    workflow_ready = False

    try:
        from graph.workflow import get_workflow

        get_workflow()

        workflow_ready = True

        components.append({"name": "langgraph_workflow", "status": "healthy"})

    except Exception as exc:
        components.append({"name": "langgraph_workflow", "status": "unhealthy", "error": str(exc)})

    try:
        from services.retriever_service import get_retriever_service

        rs = get_retriever_service()

        health = await rs.health_check()

        vs = health.get("vector_store", {})

        emb = health.get("embedder", {})

        components.append({

            "name": "faiss_index",

            "status": vs.get("status", "unhealthy"),

            "vectors": vs.get("vectors"),

            "documents": vs.get("documents"),

        })

        components.append({

            "name": "embedder",

            "status": emb.get("status", "unhealthy"),

            "model": emb.get("model"),

            "latency_ms": emb.get("latency_ms"),

        })

    except Exception as exc:
        components.append({"name": "retriever", "status": "unhealthy", "error": str(exc)})

    try:
        from services.llm_service import get_llm_service

        llm = get_llm_service()

        llm_health = await llm.health_check()

        components.append({

            "name": "gemini_llm",

            "status": llm_health.get("status", "unhealthy"),

            "model": llm_health.get("model"),

            "latency_ms": llm_health.get("latency_ms"),

        })

    except Exception as exc:
        components.append({"name": "gemini_llm", "status": "unhealthy", "error": str(exc)})

    statuses = {c["status"] for c in components}

    if all(s == "healthy" for s in statuses):
        overall = "healthy"

    elif "healthy" in statuses:
        overall = "degraded"

    else:
        overall = "unhealthy"

    return AgentHealthResponse(

        overall_status=overall,

        workflow_ready=workflow_ready,

        components=components,

    )

_FALLBACK_ANSWER = (

    "I was unable to generate a response at this time. "

    "Please check that your documents have been uploaded and try again."

)

async def _load_conversation_history(

    conversation_id: Optional[str],

    user_id: str,

    explicit_history: Optional[list],

) -> list:
    if explicit_history is not None:
        return explicit_history

    if not conversation_id:
        return []

    try:
        from services.conversation_service import get_conversation_history_for_llm

        history = await get_conversation_history_for_llm(

            conversation_id=conversation_id,

            user_id=user_id,

            limit=20,

        )

        result = []

        for turn in history:
            parts = turn.get("parts", [])

            content = parts[0] if parts else turn.get("content", "")

            result.append({"role": turn["role"], "content": content})

        logger.info(

            "Loaded %d conversation turns from conversation %s",

            len(result), conversation_id[:8] + "…",

        )

        return result

    except Exception as exc:
        logger.warning("Failed to load conversation history: %s", exc)

        return []

async def _persist_messages(

    conversation_id: Optional[str],

    user_id: str,

    user_message: str,

    assistant_message: str,

    citations: list,

) -> Optional[str]:
    try:
        from services.conversation_service import (

            create_conversation,

            append_message,

        )

        conv_id = conversation_id

        if not conv_id:
            conv = await create_conversation(user_id=user_id, title=user_message[:80])

            conv_id = conv["id"]

            logger.info("Created new conversation: %s", conv_id)

        await append_message(

            conversation_id=conv_id,

            user_id=user_id,

            role="user",

            content=user_message,

        )

        sources = [

            {

                "source_index": c["source_index"],

                "document_id":  c["document_id"],

                "file_name":    c["file_name"],

                "page":         c.get("page"),

                "chunk_id":     c["chunk_id"],

                "scope":        c.get("scope", "company"),

                "score":        c.get("score", 0.0),

            }

            for c in citations

        ]

        await append_message(

            conversation_id=conv_id,

            user_id=user_id,

            role="assistant",

            content=assistant_message,

            sources=sources or None,

        )

        return conv_id

    except Exception as exc:
        logger.warning("Failed to persist messages to conversation: %s", exc)

        return conversation_id
