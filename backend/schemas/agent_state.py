from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

class RetrievedChunk(TypedDict):
    content:      str

    document_id:  str

    file_name:    str

    page:         Optional[int]

    chunk_id:     str

    scope:        str

    score:        float

    category:     str

    user_id:      Optional[str]

class Citation(TypedDict, total=False):
    source_index:   int
    document_id:    str
    file_name:      str
    page:           Optional[int]
    page_number:    Optional[int]
    chunk_id:       str
    scope:          str
    score:          float
    full_text:      Optional[str]
    text_preview:   Optional[str]
    source_text:    Optional[str]   # Focused grounding excerpt for PDF highlighting
    evidence_spans: Optional[List[Dict[str, Any]]] # All exact evidence spans supporting the answer

class AgentState(TypedDict, total=False):
    user_id:           str

    company_id:        str

    conversation_id:   Optional[str]

    user_query:        str

    intent:            Optional[str]

    retrieval_scope:       Optional[str]

    retrieved_chunks:      List[RetrievedChunk]

    company_chunks:        List[RetrievedChunk]

    workspace_chunks:      List[RetrievedChunk]

    summaries:             List[str]

    comparison_result:     Optional[str]

    gap_analysis:          Optional[str]

    tasks:                 List[str]

    citations:             List[Citation]

    final_answer:          Optional[str]

    conversation_history:  List[Dict[str, str]]

    workflow_path:         List[str]

    errors:                List[str]

    metadata:              Dict[str, Any]

def make_initial_state(

    user_id: str,

    company_id: str,

    user_query: str,

    conversation_id: Optional[str] = None,

    retrieval_scope: str = "company",

    conversation_history: Optional[List[Dict[str, str]]] = None,

) -> AgentState:
    return AgentState(

        user_id=user_id,

        company_id=company_id,

        conversation_id=conversation_id,

        user_query=user_query,

        intent=None,

        retrieval_scope=retrieval_scope,

        retrieved_chunks=[],

        company_chunks=[],

        workspace_chunks=[],

        summaries=[],

        comparison_result=None,

        gap_analysis=None,

        tasks=[],

        citations=[],

        final_answer=None,

        conversation_history=conversation_history or [],

        workflow_path=[],

        errors=[],

        metadata={},

    )
