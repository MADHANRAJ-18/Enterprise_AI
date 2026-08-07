"""
backend/services/prompt_builder.py
─────────────────────────────────────────────────────────────
Module 6 – RAG Prompt Builder

Constructs the Gemini prompt from:
  • Retrieved document chunks (with [Source N] labels)
  • The user's question

Design principles:
  • Chunks are labelled [Source 1], [Source 2], ... so Gemini can
    reference them in its answer and we can map back to citations
  • Explicit instruction to use ONLY the provided context
  • Graceful fallback prompt when no chunks pass the threshold
  • Independent of the LLM service — swap Gemini for any other LLM
    by changing only the caller, not this module

Compatible with Module 7 (LangGraph):
  • Accepts a list of SearchResult objects from the retriever
  • Returns a plain string — the LLM node consumes it directly
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import logging
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from processing.vector_store import SearchResult

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
CHUNK_MAX_CHARS = int(os.getenv("RAG_CHUNK_MAX_CHARS", "1500"))   # truncate very large chunks
MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))  # hard cap on total context


# ── RAG System Prompt ─────────────────────────────────────────

RAG_SYSTEM_PROMPT = (
    "You are an Enterprise AI Knowledge Assistant. "
    "Your job is to answer employee questions accurately using the provided document excerpts. "
    "Rules:\n"
    "1. Answer ONLY based on the provided context. Do not use outside knowledge.\n"
    "2. If the context does not contain the answer, say clearly: "
    "'I could not find a relevant answer in the uploaded documents.'\n"
    "3. Be concise, professional, and well-structured. Use bullet points when listing items.\n"
    "4. Do NOT add inline source labels like [Source 1] — sources are shown separately.\n"
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


# ── Prompt Builder ────────────────────────────────────────────

class PromptBuilder:
    """
    Builds the final RAG prompt from retrieved chunks.

    Usage:
        from services.prompt_builder import PromptBuilder
        pb = PromptBuilder()
        context_str, system_prompt = pb.build(chunks=results, query="What is the leave policy?")
        # Then pass to llm.generate(user_prompt=query, context=context_str, system_prompt=system_prompt)
    """

    def build(
        self,
        chunks: "List[SearchResult]",
        query: str,
    ) -> tuple[str, str]:
        """
        Build the context string and system prompt for Gemini.

        Args:
            chunks: Ordered list of SearchResult from the retriever (already ranked + filtered)
            query:  The original user question (used only for logging here)

        Returns:
            Tuple of (context_str, system_prompt):
              • context_str:   The retrieved text block injected into the LLM prompt
              • system_prompt: Instruction set for Gemini (RAG vs fallback)
        """
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
        """Return a human-readable debug summary of retrieved chunks (for logging)."""
        lines = []
        for i, chunk in enumerate(chunks, 1):
            page = f" p.{chunk.page_number}" if chunk.page_number else ""
            lines.append(
                f"  [{i}] {chunk.file_name}{page} "
                f"(chunk {chunk.chunk_index}, score={chunk.score:.3f})"
            )
        return "\n".join(lines) if lines else "  (no chunks)"

    # ── Internal ──────────────────────────────────────────────

    def _format_context(self, chunks: "List[SearchResult]") -> str:
        """
        Format chunks into the context block injected into the prompt.

        Each chunk is labelled [Source N] with a header showing filename + page.
        Total context is capped at MAX_CONTEXT_CHARS to avoid token overflow.
        """
        sections: List[str] = []
        total_chars = 0

        for i, chunk in enumerate(chunks, 1):
            page_info = f", page {chunk.page_number}" if chunk.page_number else ""
            header = f"[Source {i}] {chunk.file_name}{page_info}"

            # Truncate individual chunk if very large
            text = chunk.chunk_text.strip()
            if len(text) > CHUNK_MAX_CHARS:
                text = text[:CHUNK_MAX_CHARS] + "…"

            section = f"{header}\n{text}"
            section_chars = len(section)

            # Stop adding chunks if we'd exceed the context cap
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
        """Returns the citation label string, e.g. '[Source 3]'."""
        return f"[Source {chunk_index_1based}]"


# ── Singleton accessor ────────────────────────────────────────

_builder_instance: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """Return the singleton PromptBuilder."""
    global _builder_instance
    if _builder_instance is None:
        _builder_instance = PromptBuilder()
    return _builder_instance
