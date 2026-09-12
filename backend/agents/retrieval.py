from __future__ import annotations

import asyncio

import logging

from typing import List

from graph.state import (

    AgentState,

    RetrievedChunk,

    append_to_path,

    append_error,

    search_result_to_chunk,

)

logger = logging.getLogger(__name__)

import os

DEFAULT_TOP_K                = int(os.getenv("RAG_TOP_K", "5"))

DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))

async def retrieval_node(state: AgentState) -> AgentState:
    query          = state.get("user_query", "").strip()

    scope          = state.get("retrieval_scope", "company")

    user_id        = state.get("user_id", "")

    company_id     = state.get("company_id", "")

    logger.info(

        "Retrieval: query=%r | scope=%s | user_id=%s",

        query[:60], scope, user_id[:8] + "…" if len(user_id) > 8 else user_id,

    )

    state = append_to_path(state, "retrieval")

    if scope in ("workspace", "both") and not user_id:
        msg = "Retrieval: workspace scope requested but user_id is missing — aborting"

        logger.error(msg)

        state = append_error(state, msg)

        return {**state, "retrieved_chunks": [], "company_chunks": [], "workspace_chunks": []}

    company_chunks:   List[RetrievedChunk] = []

    workspace_chunks: List[RetrievedChunk] = []

    try:
        from services.retriever_service import get_retriever_service

        retriever = get_retriever_service()

        if scope == "both":
            co_task  = _retrieve(retriever, query, "company",   user_id, company_id)

            ws_task  = _retrieve(retriever, query, "workspace", user_id, company_id)

            company_chunks, workspace_chunks = await asyncio.gather(co_task, ws_task)

        elif scope == "workspace":
            workspace_chunks = await _retrieve(retriever, query, "workspace", user_id, company_id)

        else:
            company_chunks = await _retrieve(retriever, query, "company", user_id, company_id)

    except Exception as exc:
        msg = f"Retrieval failed: {exc}"

        logger.error(msg)

        state = append_error(state, msg)

        return {**state, "retrieved_chunks": [], "company_chunks": [], "workspace_chunks": []}

    all_chunks = company_chunks + workspace_chunks

    all_chunks.sort(key=lambda c: c["score"], reverse=True)

    logger.info(

        "Retrieval complete: company=%d | workspace=%d | total=%d",

        len(company_chunks), len(workspace_chunks), len(all_chunks),

    )

    return {

        **state,

        "retrieved_chunks":  all_chunks,

        "company_chunks":    company_chunks,

        "workspace_chunks":  workspace_chunks,

    }

async def _retrieve(

    retriever,

    query: str,

    scope: str,

    user_id: str,

    company_id: str,

) -> List[RetrievedChunk]:
    try:
        result = await retriever.retrieve(

            query=query,

            top_k=DEFAULT_TOP_K,

            similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,

            scope=scope,

            user_id=user_id if scope == "workspace" else None,

            company_id=company_id or None,

        )

        return [search_result_to_chunk(r) for r in result.chunks]

    except Exception as exc:
        logger.error("Retrieval scope=%s failed: %s", scope, exc)

        return []
