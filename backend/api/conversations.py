from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from pydantic import BaseModel, Field

from services.conversation_service import (

    create_conversation,

    list_conversations,

    get_conversation,

    update_conversation_title,

    generate_and_update_title,

    delete_conversation,

    append_message,

    get_messages,

)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

class CreateConversationRequest(BaseModel):
    user_id: str = Field(..., description="Authenticated user UUID")

    title: str = Field(default="New Conversation", max_length=200)

class UpdateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)

class GenerateTitleRequest(BaseModel):
    user_id: str = Field(..., description="Authenticated user UUID")
    user_message: str = Field(..., min_length=1, max_length=2000, description="The user prompt to summarize into a title")

class AppendMessageRequest(BaseModel):
    user_id: str  = Field(..., description="Authenticated user UUID")

    role:    str  = Field(..., description="'user' or 'assistant'")

    content: str  = Field(..., min_length=1, description="Message content")

    sources: Optional[List[Dict[str, Any]]] = Field(

        default=None,

        description="Optional RAG citation dicts attached to this message",

    )

@router.post(

    "",

    status_code=status.HTTP_201_CREATED,

    summary="Create a new private conversation",

)

async def create(req: CreateConversationRequest):
    conv = await create_conversation(user_id=req.user_id, title=req.title)

    return {"success": True, "conversation": conv}

@router.get(

    "",

    summary="List conversations for a user",

)

async def list_convs(

    user_id: str = Query(..., description="Authenticated user UUID"),

):
    convs = await list_conversations(user_id=user_id)

    return {"conversations": convs, "total": len(convs)}

@router.get(

    "/{conversation_id}",

    summary="Get a single conversation",

    responses={404: {"description": "Not found"}},

)

async def get_conv(

    conversation_id: str,

    user_id: str = Query(..., description="Authenticated user UUID"),

):
    conv = await get_conversation(conversation_id=conversation_id, user_id=user_id)

    return conv

@router.patch(

    "/{conversation_id}",

    summary="Update conversation title",

    responses={404: {"description": "Not found"}},

)

async def update_title(

    conversation_id: str,

    req: UpdateConversationRequest,

    user_id: str = Query(..., description="Authenticated user UUID"),

):
    result = await update_conversation_title(

        conversation_id=conversation_id,

        user_id=user_id,

        title=req.title,

    )

    return {"success": True, **result}

@router.post(
    "/{conversation_id}/generate-title",
    summary="Dynamically generate a concise 3-5 word title using LLM",
    responses={404: {"description": "Not found"}},
)
async def generate_conv_title(
    conversation_id: str,
    req: GenerateTitleRequest,
):
    title = await generate_and_update_title(
        conversation_id=conversation_id,
        user_id=req.user_id,
        first_message=req.user_message,
    )
    return {"success": True, "title": title}

@router.delete(

    "/{conversation_id}",

    status_code=status.HTTP_204_NO_CONTENT,

    summary="Delete a conversation",

    responses={404: {"description": "Not found"}},

)

async def delete_conv(

    conversation_id: str,

    user_id: str = Query(..., description="Authenticated user UUID"),

):
    await delete_conversation(conversation_id=conversation_id, user_id=user_id)

@router.post(

    "/{conversation_id}/messages",

    status_code=status.HTTP_201_CREATED,

    summary="Append a message to a conversation",

    responses={403: {"description": "Not the conversation owner"}, 404: {"description": "Not found"}},

)

async def add_message(

    conversation_id: str,

    req: AppendMessageRequest,

):
    msg = await append_message(

        conversation_id=conversation_id,

        user_id=req.user_id,

        role=req.role,

        content=req.content,

        sources=req.sources,

    )

    return {"success": True, "message": msg}

@router.get(

    "/{conversation_id}/messages",

    summary="List messages in a conversation",

    responses={404: {"description": "Not found"}},

)

async def get_msgs(

    conversation_id: str,

    user_id: str = Query(..., description="Authenticated user UUID"),

    limit: int = Query(100, ge=1, le=500, description="Max messages to return"),

):
    msgs = await get_messages(

        conversation_id=conversation_id,

        user_id=user_id,

        limit=limit,

    )

    return {"messages": msgs, "total": len(msgs), "conversation_id": conversation_id}
