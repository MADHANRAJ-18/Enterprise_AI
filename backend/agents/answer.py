from __future__ import annotations

import logging

import os

from typing import List, Optional

from graph.state import AgentState, RetrievedChunk, append_to_path, append_error

logger = logging.getLogger(__name__)

_CHUNK_MAX = int(os.getenv("RAG_CHUNK_MAX_CHARS", "1500"))

_CTX_MAX   = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))

_QA_SYSTEM_PROMPT = (

    "You are an Enterprise AI Knowledge Assistant. "

    "Answer the employee's question using ONLY the provided document context. "

    "Rules:\n"

    "1. Answer ONLY from the provided [Source N] context — no outside knowledge.\n"

    "2. If the answer is not in the context, say: "

    "'I could not find a relevant answer in the uploaded documents.'\n"

    "3. Be concise, professional, and well-structured.\n"

    "4. Do NOT add inline [Source N] labels — citations are shown separately.\n"

    "5. Never fabricate document facts."

)

_SUMMARY_SYSTEM_PROMPT = (

    "You are an Enterprise AI Knowledge Assistant. "

    "Combine the provided document summaries into a single coherent, well-structured answer. "

    "Rules:\n"

    "1. Use ONLY the provided summaries — do not add outside knowledge.\n"

    "2. Eliminate redundancy across summaries.\n"

    "3. Use clear section headers and bullet points where appropriate.\n"

    "4. Keep the response professional and under 600 words.\n"

    "5. Do not fabricate facts."

)

_COMPARISON_ANSWER_PROMPT = (

    "You are an Enterprise AI Knowledge Assistant. "

    "Present the following comparison or gap analysis result clearly and professionally. "

    "Rules:\n"

    "1. Present the analysis as-is — do not add outside knowledge.\n"

    "2. Keep the structure (headers, bullets) from the analysis.\n"

    "3. Add a brief one-sentence executive summary at the top.\n"

    "4. Do not repeat the full original summaries — reference them briefly only.\n"

    "5. Maintain a professional, constructive tone."

)

_NO_DOCS_ANSWER = (

    "I could not find relevant information in the uploaded documents to answer your question.\n\n"

    "**Suggestions:**\n"

    "- Ensure the relevant documents have been uploaded and processed.\n"

    "- Try rephrasing your question with more specific keywords.\n"

    "- Check that you are searching in the correct scope "

    "(company documents vs. your private workspace)."

)

async def answer_node(state: AgentState) -> AgentState:
    intent             = state.get("intent", "question_answering")

    query              = state.get("user_query", "")

    retrieved_chunks   = state.get("retrieved_chunks", [])

    summaries          = state.get("summaries", [])

    comparison_result  = state.get("comparison_result")

    gap_analysis       = state.get("gap_analysis")

    conversation_history = state.get("conversation_history", [])

    state = append_to_path(state, "answer")

    logger.info(

        "Answer: intent=%s | chunks=%d | summaries=%d | has_comparison=%s",

        intent, len(retrieved_chunks), len(summaries), bool(comparison_result),

    )

    try:
        if intent in ("comparison", "gap_analysis"):
            final_answer = await _answer_comparison(

                query, intent, comparison_result or gap_analysis,

                summaries, conversation_history,

            )

        elif intent == "summarization":
            if not summaries:
                final_answer = _NO_DOCS_ANSWER

            else:
                final_answer = await _answer_summarization(

                    query, summaries, conversation_history,

                )

        else:
            if not retrieved_chunks:
                logger.info("Answer: no retrieved chunks — returning no-docs message")

                final_answer = _NO_DOCS_ANSWER

            else:
                final_answer = await _answer_qa(

                    query, retrieved_chunks, conversation_history,

                )

    except Exception as exc:
        msg = f"Answer generation failed: {exc}"

        logger.error(msg)

        state = append_error(state, msg)

        final_answer = (

            "An error occurred while generating the answer. "

            "Please try again or contact support if the issue persists."

        )

    logger.info("Answer: generated %d chars", len(final_answer))

    return {**state, "final_answer": final_answer}

async def _answer_qa(

    query: str,

    chunks: List[RetrievedChunk],

    history: List[dict],

) -> str:
    context = _format_chunks_as_context(chunks)

    llm_history = _format_history(history)

    from services.llm_service import get_llm_service

    llm = get_llm_service()

    result = await llm.generate(

        user_prompt=query,

        context=context,

        system_prompt=_QA_SYSTEM_PROMPT,

        conversation_history=llm_history,

    )

    return result.content.strip()

async def _answer_summarization(

    query: str,

    summaries: List[str],

    history: List[dict],

) -> str:
    combined = "\n\n---\n\n".join(

        f"Summary {i}:\n{s.strip()}" for i, s in enumerate(summaries, 1)

    )

    prompt = (

        f"User request: \"{query}\"\n\n"

        "Combine the following document summaries into one unified response:\n\n"

        f"{combined}"

    )

    llm_history = _format_history(history)

    from services.llm_service import get_llm_service

    llm = get_llm_service()

    result = await llm.generate(

        user_prompt=prompt,

        system_prompt=_SUMMARY_SYSTEM_PROMPT,

        conversation_history=llm_history,

    )

    return result.content.strip()

async def _answer_comparison(

    query: str,

    intent: str,

    analysis: Optional[str],

    summaries: List[str],

    history: List[dict],

) -> str:
    if not analysis:
        if summaries:
            return await _answer_summarization(query, summaries, history)

        return _NO_DOCS_ANSWER

    prompt = (

        f"User's original request: \"{query}\"\n\n"

        f"{'Gap Analysis' if intent == 'gap_analysis' else 'Comparison'} Result:\n\n"

        f"{analysis}"

    )

    llm_history = _format_history(history)

    from services.llm_service import get_llm_service

    llm = get_llm_service()

    result = await llm.generate(

        user_prompt=prompt,

        system_prompt=_COMPARISON_ANSWER_PROMPT,

        conversation_history=llm_history,

    )

    return result.content.strip()

def _format_chunks_as_context(chunks: List[RetrievedChunk]) -> str:
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

def _format_history(history: List[dict]) -> List[dict]:
    if not history:
        return []

    formatted = []

    for turn in history:
        role    = turn.get("role", "user")

        content = turn.get("content", "")

        if not content:
            continue

        if role == "assistant":
            role = "model"

        formatted.append({"role": role, "parts": [content]})

    return formatted
