from __future__ import annotations

import asyncio
import logging

from typing import Any, Dict, List, Optional, cast

from fastapi import HTTPException, status

from database.conversation_repository import (

    create_conversation as db_create_conversation,

    get_conversations as db_get_conversations,

    get_conversation as db_get_conversation,

    update_conversation_title as db_update_title,

    delete_conversation as db_delete_conversation,

    save_message as db_save_message,

    get_messages as db_get_messages,

)

from database.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# ── Sync helpers (called via asyncio.to_thread) ───────────────

def _sync_get_user_profile(user_id: str) -> Dict[str, Any]:
    supabase = get_supabase()

    result = (
        supabase.table("user_profiles")
        .select("user_id, company_id, role, full_name")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found. Please ensure account setup is complete.",
        )

    return cast(list, result.data)[0]


# ── Async service functions ───────────────────────────────────

async def get_user_profile(user_id: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_sync_get_user_profile, user_id)


async def get_user_company_id(user_id: str) -> Optional[str]:
    try:
        profile = await get_user_profile(user_id)
        return profile.get("company_id")
    except HTTPException:
        return None


async def get_user_role(user_id: str) -> str:
    try:
        profile = await get_user_profile(user_id)
        return profile.get("role", "employee")
    except HTTPException:
        return "employee"


async def require_knowledge_admin(user_id: str) -> None:
    role = await get_user_role(user_id)
    if role != "knowledge_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the Knowledge Admin role.",
        )


async def create_conversation(
    user_id: str,
    title: str = "New Conversation",
) -> Dict[str, Any]:
    company_id = await get_user_company_id(user_id)

    conv = await asyncio.to_thread(
        db_create_conversation,
        user_id=user_id,
        company_id=company_id,
        title=title,
    )

    logger.info("Conversation created: id=%s user=%s", conv["id"], user_id)
    return conv


async def list_conversations(user_id: str) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(db_get_conversations, user_id=user_id)


async def get_conversation(
    conversation_id: str,
    user_id: str,
) -> Dict[str, Any]:
    conv = await asyncio.to_thread(db_get_conversation, conversation_id, user_id)

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return conv


async def update_conversation_title(
    conversation_id: str,
    user_id: str,
    title: str,
) -> Dict[str, Any]:
    await get_conversation(conversation_id, user_id)
    await asyncio.to_thread(db_update_title, conversation_id, user_id, title)
    return {"conversation_id": conversation_id, "title": title}


async def generate_and_update_title(
    conversation_id: str,
    user_id: str,
    first_message: str,
) -> str:
    await get_conversation(conversation_id, user_id)

    msg_clean = first_message.strip()
    norm_q = msg_clean.lower().strip("!?.,")
    greetings = {"hi", "hello", "hey", "heya", "howdy", "good morning", "good afternoon", "good evening", "sup", "yo"}

    if not msg_clean:
        title = "Greeting Exchange"
    elif norm_q in greetings:
        title = "Greeting Exchange"
    else:
        try:
            from services.llm_service import get_llm_service
            llm = get_llm_service()
            prompt = (
                f"Generate a concise, descriptive 3 to 5 word topic title for a conversation that begins with this user message:\n\n"
                f"\"{msg_clean[:300]}\"\n\n"
                f"Rules:\n"
                f"- Return ONLY the plain title text (no quotes, markdown, prefixes, or punctuation).\n"
                f"- Maximum 5 words."
            )
            llm_res = await llm.generate(
                user_prompt=prompt,
                system_prompt="You are an expert conversation title generator. Output only the short title.",
            )
            raw_title = llm_res.content.strip().strip('"\'`*#.-')
            raw_title = raw_title.split("\n")[0].strip()
            title = raw_title[:60] if raw_title else (msg_clean[:40] + ("…" if len(msg_clean) > 40 else ""))
        except Exception as exc:
            logger.warning("LLM title generation failed, falling back to snippet: %s", exc)
            title = msg_clean[:40] + ("…" if len(msg_clean) > 40 else "")

    await asyncio.to_thread(db_update_title, conversation_id, user_id, title)
    logger.info("Conversation title generated: id=%s title=%r", conversation_id, title)
    return title


async def delete_conversation(
    conversation_id: str,
    user_id: str,
) -> None:
    await get_conversation(conversation_id, user_id)
    await asyncio.to_thread(db_delete_conversation, conversation_id, user_id)


async def append_message(
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    await get_conversation(conversation_id, user_id)

    if role not in ("user", "assistant"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be 'user' or 'assistant'.",
        )

    return await asyncio.to_thread(
        db_save_message,
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        content=content,
        sources=sources,
    )


async def get_messages(
    conversation_id: str,
    user_id: str,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(db_get_messages, conversation_id, user_id, limit)


async def get_conversation_history_for_llm(
    conversation_id: str,
    user_id: str,
    limit: int = 20,
) -> List[Dict[str, str]]:
    msgs = await get_messages(conversation_id, user_id, limit)

    history = []
    for msg in msgs:
        llm_role = "model" if msg["role"] == "assistant" else "user"
        history.append({"role": llm_role, "parts": [msg["content"]]})

    return history
