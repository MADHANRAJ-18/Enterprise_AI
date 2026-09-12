from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, cast
from postgrest.types import CountMethod
from database.supabase_client import get_supabase

logger = logging.getLogger(__name__)

TABLE = "document_chunks"

def save_chunks(
    chunks: List[Dict[str, Any]],
    document_id: str,
    user_id: str,
    category: str = "General",
    scope: str = "company",
    company_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not chunks:
        return []

    supabase = get_supabase()

    rows = []
    for c in chunks:
        rows.append({
            "document_id": document_id,
            "user_id":     user_id,
            "chunk_index": c["chunk_index"],
            "chunk_text":  c["chunk_text"],
            "token_count": c.get("token_count", 0),
            "char_count":  c.get("char_count", len(c["chunk_text"])),
            "page_number": c.get("page_number"),
            "category":    category,
            "scope":       scope,
            "company_id":  company_id,
        })

    result = supabase.table(TABLE).insert(rows).execute()

    if not result.data:
        logger.warning("No rows returned from Supabase insert for doc %s", document_id)

    logger.info(
        "Saved %d chunks for doc %s (scope=%s) to Supabase",
        len(result.data or []), document_id, scope,
    )
    return cast(List[Dict[str, Any]], result.data or [])

def get_chunks(
    document_id: str,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    supabase = get_supabase()
    result = (
        supabase.table(TABLE)
        .select("*")
        .eq("document_id", document_id)
        .order("chunk_index", desc=False)
        .limit(limit)
        .execute()
    )
    return cast(List[Dict[str, Any]], result.data or [])

def delete_chunks(document_id: str) -> int:
    supabase = get_supabase()
    count_result = (
        supabase.table(TABLE)
        .select("id", count=CountMethod.exact)
        .eq("document_id", document_id)
        .execute()
    )
    count = count_result.count if hasattr(count_result, "count") else 0
    supabase.table(TABLE).delete().eq("document_id", document_id).execute()
    logger.info("Deleted %d chunks for doc %s", count, document_id)
    return count or 0

def get_chunk_count_for_user(user_id: str) -> int:
    supabase = get_supabase()
    result = (
        supabase.table(TABLE)
        .select("id", count=CountMethod.exact)
        .eq("user_id", user_id)
        .execute()
    )
    return result.count if hasattr(result, "count") and result.count else 0

def get_chunk_counts_per_document(
    document_ids: List[str],
) -> Dict[str, int]:
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
    rows = cast(List[Dict[str, Any]], result.data or [])
    for row in rows:
        doc_id = str(row.get("document_id", ""))
        if doc_id:
            counts[doc_id] = counts.get(doc_id, 0) + 1

    return counts
