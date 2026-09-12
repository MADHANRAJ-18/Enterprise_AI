from __future__ import annotations

import logging

from typing import List

from graph.state import AgentState, RetrievedChunk, append_to_path, append_error

logger = logging.getLogger(__name__)

_COMPARISON_SYSTEM_PROMPT = (

    "You are an Enterprise Document Comparison Specialist. "

    "Compare the provided document summaries and produce a structured analysis. "

    "Rules:\n"

    "1. Use ONLY the provided summaries — do not use outside knowledge.\n"

    "2. Be objective and professional.\n"

    "3. Organise your analysis with clear section headers:\n"

    "   ## Key Similarities\n"

    "   ## Key Differences\n"

    "   ## Conflicts or Contradictions\n"

    "   ## Recommendations\n"

    "4. Reference source documents by name when making specific comparisons.\n"

    "5. If there are fewer than 2 summaries, note this limitation.\n"

    "6. Do not make up facts not present in the summaries."

)

_GAP_ANALYSIS_SYSTEM_PROMPT = (

    "You are an Enterprise Compliance and Gap Analysis Specialist. "

    "Compare the employee's workspace documents against company standards/guidelines "

    "and produce a structured gap analysis. "

    "Rules:\n"

    "1. Use ONLY the provided context — no outside knowledge.\n"

    "2. Be objective, constructive, and professional.\n"

    "3. Organise your analysis with clear section headers:\n"

    "   ## Alignment with Company Standards\n"

    "   ## Deviations from Company Standards\n"

    "   ## Missing Requirements\n"

    "   ## Potential Risks or Gaps\n"

    "   ## Recommendations\n"

    "4. Reference source documents by name (e.g. 'company handbook', 'project spec').\n"

    "5. Be specific — vague observations are not helpful.\n"

    "6. Do not fabricate requirements or standards not present in the context."

)

async def comparison_node(state: AgentState) -> AgentState:
    intent         = state.get("intent", "comparison")

    summaries      = state.get("summaries", [])

    company_chunks = state.get("company_chunks", [])

    workspace_chunks = state.get("workspace_chunks", [])

    query          = state.get("user_query", "")

    state = append_to_path(state, "comparison")

    logger.info("Comparison: intent=%s | summaries=%d", intent, len(summaries))

    if not summaries:
        msg = "Comparison: no summaries available — cannot perform comparison"

        logger.warning(msg)

        state = append_error(state, msg)

        result_text = (

            "Insufficient content was retrieved to perform a comparison. "

            "Please ensure the relevant documents have been uploaded and try again."

        )

        if intent == "gap_analysis":
            return {**state, "comparison_result": result_text, "gap_analysis": result_text}

        return {**state, "comparison_result": result_text}

    if intent == "gap_analysis":
        prompt, system_prompt = _build_gap_prompt(

            query, summaries, company_chunks, workspace_chunks

        )

    else:
        prompt, system_prompt = _build_comparison_prompt(query, summaries)

    try:
        from services.llm_service import get_llm_service

        llm = get_llm_service()

        result = await llm.generate(

            user_prompt=prompt,

            system_prompt=system_prompt,

        )

        analysis_text = result.content.strip()

        logger.info(

            "Comparison complete: intent=%s | length=%d chars | %.2fs",

            intent, len(analysis_text), result.processing_time,

        )

    except Exception as exc:
        msg = f"Comparison LLM call failed: {exc}"

        logger.error(msg)

        state = append_error(state, msg)

        analysis_text = (

            "The comparison analysis could not be generated due to a processing error. "

            "The individual summaries above contain the retrieved content."

        )

    if intent == "gap_analysis":
        return {**state, "comparison_result": analysis_text, "gap_analysis": analysis_text}

    return {**state, "comparison_result": analysis_text}

def _build_comparison_prompt(query: str, summaries: List[str]) -> tuple[str, str]:
    summary_blocks = []

    for i, summary in enumerate(summaries, 1):
        summary_blocks.append(f"## Document Group {i} Summary\n{summary.strip()}")

    prompt = (

        f"User's comparison request: \"{query}\"\n\n"

        "Compare the following document summaries:\n\n"

        + "\n\n---\n\n".join(summary_blocks)

        + "\n\nProvide a structured comparison analysis."

    )

    return prompt, _COMPARISON_SYSTEM_PROMPT

def _build_gap_prompt(

    query: str,

    summaries: List[str],

    company_chunks: List[RetrievedChunk],

    workspace_chunks: List[RetrievedChunk],

) -> tuple[str, str]:
    n_company   = min(len(summaries), 2) if company_chunks else 0

    n_workspace = len(summaries) - n_company

    company_summary_text   = "\n\n".join(summaries[:n_company]) if n_company > 0 else "(No company standards retrieved)"

    workspace_summary_text = "\n\n".join(summaries[n_company:]) if n_workspace > 0 else "(No workspace documents retrieved)"

    co_names  = _unique_names(company_chunks)

    ws_names  = _unique_names(workspace_chunks)

    prompt = (

        f"User's gap analysis request: \"{query}\"\n\n"

        "## Company Standards / Guidelines\n"

        f"Sources: {', '.join(co_names) if co_names else 'None'}\n\n"

        f"{company_summary_text}\n\n"

        "---\n\n"

        "## Employee Workspace Documents\n"

        f"Sources: {', '.join(ws_names) if ws_names else 'None'}\n\n"

        f"{workspace_summary_text}\n\n"

        "---\n\n"

        "Perform a gap analysis: identify where the employee's documents align with "

        "or deviate from the company standards, and highlight missing requirements."

    )

    return prompt, _GAP_ANALYSIS_SYSTEM_PROMPT

def _unique_names(chunks: List[RetrievedChunk]) -> List[str]:
    seen: set = set()

    names: List[str] = []

    for chunk in chunks:
        name = chunk["file_name"]

        if name not in seen:
            seen.add(name)

            names.append(name)

    return names
