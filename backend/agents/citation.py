from __future__ import annotations

import logging

from typing import List

from graph.state import AgentState, RetrievedChunk, Citation, append_to_path, chunks_to_citations

logger = logging.getLogger(__name__)

async def citation_node(state: AgentState) -> AgentState:
    state = append_to_path(state, "citation")

    chunks: List[RetrievedChunk] = state.get("retrieved_chunks", [])
    if not chunks:
        logger.info("Citation: no chunks — returning empty citations")
        return {**state, "citations": []}

    raw_ans = state.get("final_answer") or state.get("summary") or state.get("comparison_result") or ""
    answer_text: str = str(raw_ans) if not isinstance(raw_ans, str) else raw_ans

    from services.citation_service import optimize_citations
    doc_chunks = optimize_citations(answer_text=answer_text, chunks=chunks)

    citations: List[Citation] = [
        Citation(
            source_index=c.source_index,
            document_id=c.document_id,
            file_name=c.file_name,
            page=c.page_number,
            page_number=c.page_number,
            chunk_id=c.chunk_id,
            scope=c.scope,
            score=c.similarity,
            full_text=c.full_text,
            text_preview=c.text_preview,
            source_text=c.source_text,   # Focused grounding excerpt for PDF highlight
            evidence_spans=[s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in (c.evidence_spans or [])],
        )
        for c in doc_chunks
    ]

    logger.info(
        "Citation: extracted %d relevant citations from %d retrieved chunks",
        len(citations), len(chunks),
    )

    return {**state, "citations": citations}
