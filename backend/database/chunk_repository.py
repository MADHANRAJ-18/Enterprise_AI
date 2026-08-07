"""
backend/database/chunk_repository.py
─────────────────────────────────────────────────────────────
Database operations for the document_chunks table.

Each row in document_chunks represents one text chunk with:
  - FK to documents.id
  - FK to auth.users.id
  - chunk_index, chunk_text, page_number, token_count, category
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional

from database.supabase_client import get_supabase

logger = logging.getLogger(__name__)

TABLE = "document_chunks"


def save_chunks(
    chunks: List[Dict[str, Any]],
    document_id: str,
    user_id: str,
    category: str = "General",
) -> List[Dict[str, Any]]:
    """
    Batch-insert chunk rows into the document_chunks table.

    Args:
        chunks:      List of dicts with keys: chunk_index, chunk_text,
                     page_number (optional), token_count (optional)
        document_id: Supabase document UUID (FK → documents.id)
        user_id:     Authenticated user UUID (FK → auth.users.id)
        category:    Document category (copied from parent document)

    Returns:
        List of inserted rows (with server-generated IDs and timestamps)

    Raises:
        RuntimeError: on database error
    """
    if not chunks:
        return []

    rows = [
        {
            "document_id": document_id,
            "user_id": user_id,
            "chunk_index": chunk["chunk_index"],
            "chunk_text": chunk["chunk_text"],
            "page_number": chunk.get("page_number"),
            "token_count": chunk.get("token_count"),
            "category": category,
        }
        for chunk in chunks
    ]

    supabase = get_supabase()
    result = supabase.table(TABLE).insert(rows).execute()

    if not result.data:
        raise RuntimeError(
            f"Failed to insert chunks for document {document_id}: "
            "Supabase returned no data."
        )

    logger.info(
        "Saved %d chunks for doc %s to Supabase",
        len(result.data), document_id,
    )
    return result.data


def get_chunks(
    document_id: str,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    Fetch all chunks for a document, ordered by chunk_index.

    Args:
        document_id: Supabase document UUID
        limit:       Max rows to return (safety cap)

    Returns:
        List of chunk rows
    """
    supabase = get_supabase()
    result = (
        supabase.table(TABLE)
        .select("*")
        .eq("document_id", document_id)
        .order("chunk_index", desc=False)
        .limit(limit)
        .execute()
    )
    return result.data or []


def delete_chunks(document_id: str) -> int:
    """
    Delete all chunks for a document.

    Returns:
        Number of rows deleted (approximate — Supabase may not return exact count)
    """
    supabase = get_supabase()

    # Count first for accurate reporting
    count_result = (
        supabase.table(TABLE)
        .select("id", count="exact")
        .eq("document_id", document_id)
        .execute()
    )
    count = count_result.count if hasattr(count_result, "count") else 0

    # Delete
    supabase.table(TABLE).delete().eq("document_id", document_id).execute()

    logger.info("Deleted %d chunks for doc %s", count, document_id)
    return count or 0


def get_chunk_count_for_user(user_id: str) -> int:
    """Returns the total number of chunks indexed for a user."""
    supabase = get_supabase()
    result = (
        supabase.table(TABLE)
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return result.count if hasattr(result, "count") and result.count else 0


def get_chunk_counts_per_document(
    document_ids: List[str],
) -> Dict[str, int]:
    """
    Returns a mapping of document_id → chunk_count for a list of docs.
    Efficient bulk query instead of N individual queries.
    """
    if not document_ids:
        return {}

    supabase = get_supabase()
    result = (
        supabase.table(TABLE)
        .select("document_id")
        .in_("document_id", document_ids)
        .execute()
    )

    counts: Dict[str, int] = {}
    for row in (result.data or []):
        doc_id = row["document_id"]
        counts[doc_id] = counts.get(doc_id, 0) + 1

    return counts
