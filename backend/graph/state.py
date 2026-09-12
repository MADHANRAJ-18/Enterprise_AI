from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

from schemas.agent_state import AgentState, RetrievedChunk, Citation, make_initial_state

if TYPE_CHECKING:
    from processing.vector_store import SearchResult

__all__ = [

    "AgentState",

    "RetrievedChunk",

    "Citation",

    "make_initial_state",

    "append_to_path",

    "append_error",

    "search_result_to_chunk",

    "chunks_to_citations",

]

def append_to_path(state: AgentState, node_name: str) -> AgentState:
    path = list(state.get("workflow_path", []))

    path.append(node_name)

    return {**state, "workflow_path": path}

def append_error(state: AgentState, error_msg: str) -> AgentState:
    errors = list(state.get("errors", []))

    errors.append(error_msg)

    return {**state, "errors": errors}

def search_result_to_chunk(result: "SearchResult") -> RetrievedChunk:
    return RetrievedChunk(

        content=result.chunk_text,

        document_id=result.document_id,

        file_name=result.file_name,

        page=result.page_number,

        chunk_id=result.chunk_id,

        scope=getattr(result, "scope", "company"),

        score=round(result.score, 4),

        category=getattr(result, "category", ""),

        user_id=getattr(result, "user_id", None),

    )

def chunks_to_citations(chunks: List[RetrievedChunk]) -> List[Citation]:
    seen: set = set()

    citations: List[Citation] = []

    for i, chunk in enumerate(chunks, 1):
        cid = chunk["chunk_id"]

        if cid in seen:
            continue

        seen.add(cid)

        citations.append(Citation(

            source_index=i,

            document_id=chunk["document_id"],

            file_name=chunk["file_name"],

            page=chunk.get("page"),

            chunk_id=cid,

            scope=chunk.get("scope", "company"),

            score=chunk.get("score", 0.0),

        ))

    return citations
