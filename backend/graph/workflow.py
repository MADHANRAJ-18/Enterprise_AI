from __future__ import annotations

import logging

from typing import Optional

from langgraph.graph import StateGraph, START, END

from schemas.agent_state import AgentState

from agents.coordinator import coordinator_node

from agents.retrieval    import retrieval_node

from agents.summarizer   import summarizer_node

from agents.comparison   import comparison_node

from agents.citation     import citation_node

from agents.answer       import answer_node

logger = logging.getLogger(__name__)

N_COORDINATOR = "coordinator"

N_RETRIEVAL   = "retrieval"

N_SUMMARIZER  = "summarizer"

N_COMPARISON  = "comparison"

N_CITATION    = "citation"

N_ANSWER      = "answer"

ROUTE_QA       = "qa"

ROUTE_SUMMARIZE = "summarize"

ROUTE_COMPARE  = "compare"

ROUTE_CITE     = "cite"

def route_after_retrieval(state: AgentState) -> str:
    intent = state.get("intent", "question_answering")

    logger.debug("route_after_retrieval: intent=%s", intent)

    if intent == "question_answering":
        return ROUTE_QA

    return ROUTE_SUMMARIZE

def route_after_summarizer(state: AgentState) -> str:
    intent = state.get("intent", "summarization")

    logger.debug("route_after_summarizer: intent=%s", intent)

    if intent in ("comparison", "gap_analysis"):
        return ROUTE_COMPARE

    return ROUTE_CITE

def build_workflow():
    graph = StateGraph(AgentState)  # type: ignore[arg-type]

    graph.add_node(N_COORDINATOR, coordinator_node)

    graph.add_node(N_RETRIEVAL,   retrieval_node)

    graph.add_node(N_SUMMARIZER,  summarizer_node)

    graph.add_node(N_COMPARISON,  comparison_node)

    graph.add_node(N_CITATION,    citation_node)

    graph.add_node(N_ANSWER,      answer_node)

    graph.add_edge(START, N_COORDINATOR)

    graph.add_edge(N_COORDINATOR, N_RETRIEVAL)

    graph.add_conditional_edges(

        N_RETRIEVAL,

        route_after_retrieval,

        {

            ROUTE_QA:       N_CITATION,

            ROUTE_SUMMARIZE: N_SUMMARIZER,

        },

    )

    graph.add_conditional_edges(

        N_SUMMARIZER,

        route_after_summarizer,

        {

            ROUTE_COMPARE: N_COMPARISON,

            ROUTE_CITE:    N_CITATION,

        },

    )

    graph.add_edge(N_COMPARISON, N_CITATION)

    graph.add_edge(N_CITATION, N_ANSWER)

    graph.add_edge(N_ANSWER,   END)

    compiled = graph.compile()

    logger.info(

        "LangGraph workflow compiled: %d nodes | coordinator→retrieval→[summarizer]→[comparison]→citation→answer",

        len(graph.nodes),

    )

    return compiled

_workflow_instance = None

def get_workflow():
    global _workflow_instance

    if _workflow_instance is None:
        logger.info("Building LangGraph workflow (first call)…")

        _workflow_instance = build_workflow()

    return _workflow_instance

def reset_workflow() -> None:
    global _workflow_instance

    _workflow_instance = None
