from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional, cast

from database.supabase_client import get_supabase

logger = logging.getLogger(__name__)

CONV_TABLE = "conversations"

MSG_TABLE  = "messages"

def create_conversation(

    user_id: str,

    company_id: Optional[str],

    title: str = "New Conversation",

) -> Dict[str, Any]:
    supabase = get_supabase()

    result = (

        supabase.table(CONV_TABLE)

        .insert({

            "user_id":    user_id,

            "company_id": company_id,

            "title":      title,

        })

        .execute()

    )

    rows = cast(List[Dict[str, Any]], result.data)

    logger.info("Conversation created: id=%s, user=%s", rows[0]["id"], user_id)

    return rows[0]

def get_conversations(

    user_id: str,

    limit: int = 50,

) -> List[Dict[str, Any]]:
    supabase = get_supabase()

    result = (

        supabase.table(CONV_TABLE)

        .select("*")

        .eq("user_id", user_id)

        .order("updated_at", desc=True)

        .limit(limit)

        .execute()

    )

    return cast(List[Dict[str, Any]], result.data or [])

def get_conversation(

    conversation_id: str,

    user_id: str,

) -> Optional[Dict[str, Any]]:
    supabase = get_supabase()

    result = (

        supabase.table(CONV_TABLE)

        .select("*")

        .eq("id", conversation_id)

        .eq("user_id", user_id)

        .limit(1)

        .execute()

    )

    rows = cast(List[Dict[str, Any]], result.data or [])

    return rows[0] if rows else None

def update_conversation_title(

    conversation_id: str,

    user_id: str,

    title: str,

) -> bool:
    supabase = get_supabase()

    result = (

        supabase.table(CONV_TABLE)

        .update({"title": title})

        .eq("id", conversation_id)

        .eq("user_id", user_id)

        .execute()

    )

    return bool(result.data)

def delete_conversation(

    conversation_id: str,

    user_id: str,

) -> bool:
    supabase = get_supabase()

    supabase.table(CONV_TABLE).delete().eq("id", conversation_id).eq("user_id", user_id).execute()

    logger.info("Conversation deleted: id=%s, user=%s", conversation_id, user_id)

    return True

def touch_conversation(conversation_id: str) -> None:
    supabase = get_supabase()

    from datetime import datetime, timezone

    supabase.table(CONV_TABLE).update(

        {"updated_at": datetime.now(timezone.utc).isoformat()}

    ).eq("id", conversation_id).execute()

def save_message(

    conversation_id: str,

    user_id: str,

    role: str,

    content: str,

    sources: Optional[List[Dict[str, Any]]] = None,

) -> Dict[str, Any]:
    supabase = get_supabase()

    result = (

        supabase.table(MSG_TABLE)

        .insert({

            "conversation_id": conversation_id,

            "user_id":         user_id,

            "role":            role,

            "content":         content,

            "sources":         sources or [],

        })

        .execute()

    )

    if not result.data:
        raise RuntimeError(f"Failed to save message for conversation {conversation_id}.")

    touch_conversation(conversation_id)

    return cast(List[Dict[str, Any]], result.data)[0]

def get_messages(

    conversation_id: str,

    user_id: str,

    limit: int = 100,

) -> List[Dict[str, Any]]:
    conv = get_conversation(conversation_id, user_id)

    if not conv:
        logger.warning(

            "get_messages: conversation %s not found or not owned by user %s",

            conversation_id, user_id,

        )

        return []

    supabase = get_supabase()

    result = (

        supabase.table(MSG_TABLE)

        .select("*")

        .eq("conversation_id", conversation_id)

        .order("created_at", desc=False)

        .limit(limit)

        .execute()

    )

    return cast(List[Dict[str, Any]], result.data or [])

def delete_messages(conversation_id: str) -> None:
    supabase = get_supabase()

    supabase.table(MSG_TABLE).delete().eq("conversation_id", conversation_id).execute()
