from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status, Body

from models.notification import (
    NotificationListResponse,
    NotificationItem,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
    MarkReadRequest,
)
from services.notification_service import get_notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="Get notifications for a user",
)
async def list_notifications(
    user_id: str = Query(..., description="Authenticated user UUID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
) -> NotificationListResponse:
    ns = get_notification_service()
    data = await ns.get_user_notifications(
        user_id=user_id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    items = [
        NotificationItem(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            company_id=str(r["company_id"]) if r.get("company_id") else None,
            type=r.get("type", "company_document_update"),
            title=r.get("title", ""),
            message=r.get("message", ""),
            related_document_id=str(r["related_document_id"]) if r.get("related_document_id") else None,
            is_read=bool(r.get("is_read", False)),
            created_at=str(r.get("created_at", "")),
        )
        for r in data["notifications"]
    ]
    return NotificationListResponse(
        notifications=items,
        unread_count=data["unread_count"],
        total=data["total"],
    )


@router.patch(
    "/{notification_id}/read",
    summary="Mark single notification as read",
)
async def mark_read(
    notification_id: str,
    user_id: str = Query(..., description="Authenticated user UUID"),
):
    ns = get_notification_service()
    await ns.mark_notification_as_read(user_id=user_id, notification_id=notification_id)
    return {"success": True, "notification_id": notification_id, "is_read": True}


@router.patch(
    "/read-all",
    summary="Mark all notifications as read for a user",
)
async def mark_all_read(
    user_id: str = Query(..., description="Authenticated user UUID"),
):
    ns = get_notification_service()
    await ns.mark_all_notifications_as_read(user_id=user_id)
    return {"success": True, "message": "All notifications marked as read"}


@router.get(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    summary="Get user notification preferences",
)
async def get_preferences(
    user_id: str = Query(..., description="Authenticated user UUID"),
) -> NotificationPreferenceResponse:
    ns = get_notification_service()
    pref = await ns.get_user_preference(user_id=user_id)
    return NotificationPreferenceResponse(
        user_id=pref["user_id"],
        company_file_updates=pref["company_file_updates"],
        updated_at=pref.get("updated_at"),
    )


@router.put(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    summary="Update user notification preferences",
)
async def update_preferences(
    user_id: str = Query(..., description="Authenticated user UUID"),
    body: NotificationPreferenceUpdateRequest = Body(...),
) -> NotificationPreferenceResponse:
    ns = get_notification_service()
    pref = await ns.update_user_preference(
        user_id=user_id,
        company_file_updates=body.company_file_updates,
    )
    return NotificationPreferenceResponse(
        user_id=pref["user_id"],
        company_file_updates=pref["company_file_updates"],
        updated_at=pref.get("updated_at"),
    )
