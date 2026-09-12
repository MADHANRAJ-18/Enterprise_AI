from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class NotificationItem(BaseModel):
    id: str
    user_id: str
    company_id: Optional[str] = None
    type: str = Field(default="company_document_update")
    title: str
    message: str
    related_document_id: Optional[str] = None
    is_read: bool = False
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: List[NotificationItem] = Field(default_factory=list)
    unread_count: int = 0
    total: int = 0


class NotificationPreferenceResponse(BaseModel):
    user_id: str
    company_file_updates: bool = True
    updated_at: Optional[str] = None


class NotificationPreferenceUpdateRequest(BaseModel):
    company_file_updates: bool = Field(
        ...,
        description="Enable/disable notifications when company documents are added, updated, or removed."
    )


class MarkReadRequest(BaseModel):
    notification_ids: Optional[List[str]] = Field(
        default=None,
        description="List of notification IDs to mark as read. If omitted or empty, marks all as read."
    )
