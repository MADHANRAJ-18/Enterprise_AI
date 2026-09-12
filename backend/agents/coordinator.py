from __future__ import annotations

import logging

import re

from typing import Optional

from graph.state import AgentState, append_to_path, append_error

logger = logging.getLogger(__name__)

_SUMMARIZE_KEYWORDS = {

    "summarize", "summarise", "summary", "summarization",

    "overview", "brief", "tldr", "tl;dr", "highlight",

    "key points", "main points", "outline",

}

_COMPARISON_KEYWORDS = {

    "compare", "comparison", "contrast", "difference", "differences",

    "similarities", "versus", "vs", "vs.", "which is better",

    "how do they differ", "side by side",

}

_GAP_KEYWORDS = {

    "gap", "gaps", "gap analysis", "deviation", "deviations",

    "comply", "compliance", "compliant", "follows", "adheres",

    "standard", "standards", "check if", "audit", "against",

    "my project", "my work", "my document", "my doc",

}

_WORKSPACE_KEYWORDS = {

    "my project", "my document", "my doc", "my file", "my work",

    "my notes", "my report", "my draft", "my workspace",

    "i uploaded", "i have uploaded", "i shared",

}

_COMPANY_KEYWORDS = {

    "company", "company policy", "company standard", "company guideline",

    "organization", "organisation", "enterprise", "corporate",

    "hr", "handbook", "policy", "policies", "guidelines", "procedure",

    "our leave", "our vacation", "our benefits", "architecture guide",

}

_COORD_SYSTEM_PROMPT = """You are a routing classifier for an Enterprise Knowledge Assistant.
Classify the user query into EXACTLY ONE intent and ONE scope.

INTENT options:
- question_answering  : direct factual question needing a specific answer
- summarization       : request to summarize one or more documents
- comparison          : request to compare multiple documents or policies
- gap_analysis        : compare employee workspace documents against company standards

SCOPE options:
- company    : query is about shared company knowledge (policies, guidelines, standards)
- workspace  : query is about the employee's own private documents/projects
- both       : query requires BOTH company knowledge AND employee workspace (typical for gap_analysis)

Reply ONLY in this exact JSON format (no markdown, no explanation):
{"intent": "<intent>", "scope": "<scope>"}"""

async def coordinator_node(state: AgentState) -> AgentState:
    query = state.get("user_query", "").strip()

    logger.info("Coordinator: classifying query=%r", query[:80])

    state = append_to_path(state, "coordinator")

    if not query:
        state = append_error(state, "Coordinator: empty user_query")

        return {**state, "intent": "question_answering", "retrieval_scope": "company"}

    intent, scope = await _llm_classify(query, state.get("conversation_history", []))

    if not intent or not scope:
        logger.info("Coordinator: LLM classification failed — using keyword heuristic")

        intent, scope = _heuristic_classify(query)

    if intent == "gap_analysis" and scope != "both":
        scope = "both"

    logger.info("Coordinator: intent=%s | scope=%s", intent, scope)

    return {**state, "intent": intent, "retrieval_scope": scope}

async def _llm_classify(

    query: str,

    history: list,

) -> tuple[Optional[str], Optional[str]]:
    try:
        import json

        from services.llm_service import get_llm_service

        llm = get_llm_service()

        history_ctx = ""

        if history:
            recent = history[-4:]

            turns = [f"{t['role'].upper()}: {t['content'][:200]}" for t in recent]

            history_ctx = "\nPrior conversation context:\n" + "\n".join(turns) + "\n"

        prompt = (

            f"{history_ctx}"

            f"User query: {query}\n\n"

            "Classify the intent and scope. Reply only with the JSON."

        )

        result = await llm.generate(

            user_prompt=prompt,

            system_prompt=_COORD_SYSTEM_PROMPT,

        )

        text = result.content.strip()

        text = re.sub(r"```(?:json)?", "", text).strip().strip("`")

        parsed = json.loads(text)

        intent = parsed.get("intent", "").strip().lower()

        scope  = parsed.get("scope", "").strip().lower()

        valid_intents = {"question_answering", "summarization", "comparison", "gap_analysis"}

        valid_scopes  = {"company", "workspace", "both"}

        if intent in valid_intents and scope in valid_scopes:
            return intent, scope

        logger.warning("Coordinator LLM returned invalid values: intent=%r scope=%r", intent, scope)

        return None, None

    except Exception as exc:
        logger.warning("Coordinator LLM classification failed: %s", exc)

        return None, None

def _heuristic_classify(query: str) -> tuple[str, str]:
    q = query.lower()

    has_workspace = any(kw in q for kw in _WORKSPACE_KEYWORDS)

    has_company   = any(kw in q for kw in _COMPANY_KEYWORDS)

    has_compare   = any(kw in q for kw in _COMPARISON_KEYWORDS)

    has_gap       = any(kw in q for kw in _GAP_KEYWORDS)

    has_summarize = any(kw in q for kw in _SUMMARIZE_KEYWORDS)

    is_gap_analysis = (

        (has_workspace and has_company)

        or (has_gap and has_compare and (has_workspace or has_company))

        or (has_gap and has_workspace and has_company)

    )

    if is_gap_analysis:
        intent = "gap_analysis"

    elif has_compare:
        intent = "comparison"

    elif has_summarize:
        intent = "summarization"

    else:
        intent = "question_answering"

    if intent == "gap_analysis":
        scope = "both"

    elif has_workspace and has_company:
        scope = "both"

    elif has_workspace:
        scope = "workspace"

    else:
        scope = "company"

    return intent, scope
