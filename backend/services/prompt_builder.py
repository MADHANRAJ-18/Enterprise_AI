from __future__ import annotations

import os

import logging

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from processing.vector_store import SearchResult

logger = logging.getLogger(__name__)

CHUNK_MAX_CHARS = int(os.getenv("RAG_CHUNK_MAX_CHARS", "1500"))

MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))

RAG_SYSTEM_PROMPT = (
    "You are an Enterprise AI Knowledge Assistant. "
    "Your job is to answer employee questions accurately using the provided document excerpts. "
    "Rules:\n"
    "1. Answer ONLY based on the provided context. Do not use outside knowledge.\n"
    "2. If the context does not contain the answer, say clearly: "
    "'I could not find a relevant answer in the uploaded documents.'\n"
    "3. Be concise, professional, and well-structured. Use bullet points when listing items.\n"
    "4. Add inline citations like [Source 1], [Source 2] immediately after statements or facts drawn from specific documents. Only cite sources that you actually used in your answer.\n"
    "5. Never make up information or hallucinate facts."
)

FALLBACK_SYSTEM_PROMPT = (

    "You are an Enterprise AI Knowledge Assistant. "

    "No relevant documents were found for the user's question. "

    "Politely inform the user that no matching information was found in the uploaded documents, "

    "and suggest they upload relevant documents or rephrase their question. "

    "Do not answer from general knowledge — only reference the knowledge base."

)

DEFAULT_ASSISTANT_PROMPT = (

    "You are an Enterprise AI Knowledge Assistant. "

    "You help employees find accurate information from company documents, "

    "policies, and knowledge bases. "

    "Be concise, professional, friendly, and helpful."

)

class PromptBuilder:
    def build(

        self,

        chunks: "List[SearchResult]",

        query: str,

    ) -> tuple[str, str]:
        if not chunks:
            from services.retriever_service import CONVERSATIONAL_QUERIES

            norm_q = query.strip().lower().strip("!?.,")

            if norm_q in CONVERSATIONAL_QUERIES or len(norm_q) <= 2:
                logger.info("PromptBuilder: conversational query — using default assistant prompt")

                return "", DEFAULT_ASSISTANT_PROMPT

            logger.info("PromptBuilder: no chunks — using fallback prompt")

            return "", FALLBACK_SYSTEM_PROMPT

        context_str = self._format_context(chunks)

        logger.info(

            "PromptBuilder: built context from %d chunks (%d chars)",

            len(chunks), len(context_str),

        )

        return context_str, RAG_SYSTEM_PROMPT

    def build_search_summary(self, chunks: "List[SearchResult]") -> str:
        lines = []

        for i, chunk in enumerate(chunks, 1):
            page = f" p.{chunk.page_number}" if chunk.page_number else ""

            lines.append(

                f"  [{i}] {chunk.file_name}{page} "

                f"(chunk {chunk.chunk_index}, score={chunk.score:.3f})"

            )

        return "\n".join(lines) if lines else "  (no chunks)"

    def _format_context(self, chunks: "List[SearchResult]") -> str:
        sections: List[str] = []

        total_chars = 0

        for i, chunk in enumerate(chunks, 1):
            page_info = f", page {chunk.page_number}" if chunk.page_number else ""

            header = f"[Source {i}] {chunk.file_name}{page_info}"

            text = chunk.chunk_text.strip()

            if len(text) > CHUNK_MAX_CHARS:
                text = text[:CHUNK_MAX_CHARS] + "…"

            section = f"{header}\n{text}"

            section_chars = len(section)

            if total_chars + section_chars > MAX_CONTEXT_CHARS and sections:
                logger.warning(

                    "Context cap reached at chunk %d/%d (%d chars). Truncating.",

                    i, len(chunks), total_chars,

                )

                break

            sections.append(section)

            total_chars += section_chars

        return "\n\n".join(sections)

    def chunk_to_citation_label(self, chunk_index_1based: int) -> str:
        return f"[Source {chunk_index_1based}]"

_builder_instance: Optional[PromptBuilder] = None

def get_prompt_builder() -> PromptBuilder:
    global _builder_instance

    if _builder_instance is None:
        _builder_instance = PromptBuilder()

    return _builder_instance
