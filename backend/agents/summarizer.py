from __future__ import annotations

import asyncio

import logging

from typing import List, Optional

from graph.state import AgentState, RetrievedChunk, append_to_path, append_error

logger = logging.getLogger(__name__)

NUM_SUMMARIZERS = 3

_SUMMARIZER_SYSTEM_PROMPT = (

    "You are an Enterprise Document Summarizer. "

    "Produce a concise, structured summary of the provided document excerpts. "

    "Rules:\n"

    "1. Base the summary ONLY on the provided document excerpts.\n"

    "2. Use bullet points for key facts. Include section headers where appropriate.\n"

    "3. Reference the source label (e.g. [Source 1]) when citing specific content.\n"

    "4. Do NOT invent facts not present in the excerpts.\n"

    "5. If excerpts are from the same document, produce one unified summary.\n"

    "6. Keep the summary professional and under 400 words."

)

async def summarizer_node(state: AgentState) -> AgentState:
    chunks: List[RetrievedChunk] = state.get("retrieved_chunks", [])

    query = state.get("user_query", "")

    state = append_to_path(state, "summarizer")

    if not chunks:
        logger.warning("Summarizer: no retrieved chunks — skipping")

        state = append_error(state, "Summarizer: no documents to summarize")

        return {**state, "summaries": ["No relevant documents were found to summarize."]}

    chunk_groups = _distribute_chunks(chunks, NUM_SUMMARIZERS)

    logger.info(

        "Summarizer: distributing %d chunks → [%s]",

        len(chunks),

        ", ".join(str(len(g)) for g in chunk_groups),

    )

    tasks = []

    active_indices = []

    for idx, group in enumerate(chunk_groups):
        if group:
            tasks.append(_run_single_summarizer(idx + 1, group, query))

            active_indices.append(idx)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    summaries: List[str] = []

    for i, result in enumerate(results):
        if isinstance(result, (Exception, BaseException)):
            msg = f"Summarizer {active_indices[i] + 1} failed: {result}"
            logger.error(msg)
            state = append_error(state, msg)
        elif isinstance(result, str) and result:
            summaries.append(result)

    if not summaries:
        summaries = ["Summarization failed. Please check the document content or try again."]

        state = append_error(state, "All summarizers returned empty results")

    logger.info("Summarizer: produced %d summaries", len(summaries))

    return {**state, "summaries": summaries}

def _distribute_chunks(

    chunks: List[RetrievedChunk],

    n: int,

) -> List[List[RetrievedChunk]]:
    doc_groups: dict[str, List[RetrievedChunk]] = {}

    for chunk in chunks:
        doc_id = chunk["document_id"]

        if doc_id not in doc_groups:
            doc_groups[doc_id] = []

        doc_groups[doc_id].append(chunk)

    doc_list = list(doc_groups.values())

    slots: List[List[RetrievedChunk]] = [[] for _ in range(n)]

    for i, doc_chunk_list in enumerate(doc_list):
        slots[i % n].extend(doc_chunk_list)

    return slots

async def _run_single_summarizer(

    summarizer_id: int,

    chunks: List[RetrievedChunk],

    original_query: str,

) -> Optional[str]:
    context = _format_chunks_for_summarizer(chunks)

    doc_names = _unique_doc_names(chunks)

    prompt = (

        f"The user requested: \"{original_query}\"\n\n"

        f"Summarise the following document excerpt(s) from: {', '.join(doc_names)}\n\n"

        f"{context}"

    )

    logger.debug(

        "Summarizer %d: calling Gemini with %d chunks (%d chars context)",

        summarizer_id, len(chunks), len(context),

    )

    try:
        from services.llm_service import get_llm_service

        llm = get_llm_service()

        result = await llm.generate(

            user_prompt=prompt,

            system_prompt=_SUMMARIZER_SYSTEM_PROMPT,

        )

        summary = result.content.strip()

        logger.info(

            "Summarizer %d: complete (%d chars, %.2fs)",

            summarizer_id, len(summary), result.processing_time,

        )

        return summary

    except Exception as exc:
        logger.error("Summarizer %d LLM call failed: %s", summarizer_id, exc)

        raise

import os

_CHUNK_MAX = int(os.getenv("RAG_CHUNK_MAX_CHARS", "1500"))

_CTX_MAX   = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))

def _format_chunks_for_summarizer(chunks: List[RetrievedChunk]) -> str:
    sections: List[str] = []

    total = 0

    for i, chunk in enumerate(chunks, 1):
        page_info = f", page {chunk['page']}" if chunk.get("page") else ""

        header = f"[Source {i}] {chunk['file_name']}{page_info}"

        text = chunk["content"].strip()

        if len(text) > _CHUNK_MAX:
            text = text[:_CHUNK_MAX] + "…"

        section = f"{header}\n{text}"

        if total + len(section) > _CTX_MAX and sections:
            break

        sections.append(section)

        total += len(section)

    return "\n\n".join(sections)

def _unique_doc_names(chunks: List[RetrievedChunk]) -> List[str]:
    seen: set = set()

    names: List[str] = []

    for chunk in chunks:
        name = chunk["file_name"]

        if name not in seen:
            seen.add(name)

            names.append(name)

    return names
