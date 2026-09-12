from __future__ import annotations

import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set, cast

from database.supabase_client import get_supabase
from services.email_service import get_email_service

logger = logging.getLogger(__name__)

# Sliding deduplication window: (doc_id, change_type, time_bucket_15s)
_recent_events: Set[str] = set()
_event_timestamps: Dict[str, float] = {}


def _cleanup_old_events():
    now = time.time()
    expired = [k for k, ts in _event_timestamps.items() if now - ts > 60]
    for k in expired:
        _event_timestamps.pop(k, None)
        _recent_events.discard(k)


class NotificationService:
    def __init__(self):
        self.supabase = get_supabase()
        self.email_service = get_email_service()

    async def notify_company_document_change(
        self,
        company_id: str,
        document_id: str,
        file_name: str,
        change_type: str,
        actor_user_id: str,
    ) -> Dict[str, Any]:
        """
        Notify all authorized employees in the company about document add/update/remove.
        Excludes the user who performed the operation (actor_user_id).
        Checks user preferences (company_file_updates) before delivering notifications/emails.
        """
        if not company_id:
            logger.warning("Notification skipped: missing company_id for doc %s", document_id)
            return {"success": False, "reason": "missing_company_id"}

        change_type = change_type.lower()
        if change_type not in ("added", "updated", "removed"):
            change_type = "updated"

        # Idempotency check: prevent double-firing in rapid succession
        _cleanup_old_events()
        event_key = f"{company_id}:{document_id}:{change_type}"
        now = time.time()
        if event_key in _recent_events and (now - _event_timestamps.get(event_key, 0) < 15):
            logger.info("Duplicate notification suppressed for %s", event_key)
            return {"success": True, "suppressed_duplicate": True}

        _recent_events.add(event_key)
        _event_timestamps[event_key] = now

        logger.info(
            "Processing company document notification: company=%s | doc=%s (%s) | event=%s | actor=%s",
            company_id, document_id, file_name, change_type, actor_user_id,
        )

        # 1. Fetch all company members from user_profiles
        try:
            profiles_res = (
                self.supabase.table("user_profiles")
                .select("user_id, role, full_name")
                .eq("company_id", company_id)
                .execute()
            )
            members = cast(List[Dict[str, Any]], profiles_res.data or [])
        except Exception as exc:
            logger.error("Failed to query user_profiles for company %s: %s", company_id, exc)
            return {"success": False, "error": str(exc)}

        if not members:
            logger.info("No company members found for company_id %s", company_id)
            return {"success": True, "notified_count": 0}

        # 2. Exclude the actor who made the change
        candidate_users = [
            m for m in members if str(m.get("user_id", "")) != actor_user_id
        ]
        if not candidate_users:
            logger.info("No recipients after excluding actor %s", actor_user_id)
            return {"success": True, "notified_count": 0}

        candidate_user_ids = [str(m.get("user_id", "")) for m in candidate_users if m.get("user_id")]

        # 3. Query user preferences for all candidate users
        prefs_map: Dict[str, bool] = {}
        try:
            prefs_res = (
                self.supabase.table("user_preferences")
                .select("user_id, company_file_updates")
                .in_("user_id", candidate_user_ids)
                .execute()
            )
            for row in cast(List[Dict[str, Any]], prefs_res.data or []):
                uid_str = str(row.get("user_id", ""))
                if uid_str:
                    prefs_map[uid_str] = bool(row.get("company_file_updates", True))
        except Exception as exc:
            logger.warning("Could not fetch user_preferences: %s. Using default=True", exc)

        # 4. Filter eligible users (company_file_updates is True by default)
        eligible_users = [
            u for u in candidate_users
            if prefs_map.get(str(u.get("user_id", "")), True) is True
        ]

        if not eligible_users:
            logger.info("All candidates have company_file_updates preference turned OFF")
            return {"success": True, "notified_count": 0}

        # 5. Build titles and messages
        action_verb = "added and is now available in" if change_type == "added" else "updated and is now available in" if change_type == "updated" else "removed from"
        title = f"Company document {change_type}"
        message = f"'{file_name}' was {action_verb} Company Knowledge."

        # 6. Create in-app notification records
        in_app_rows = [
            {
                "user_id": str(u.get("user_id", "")),
                "company_id": company_id,
                "type": "company_document_update",
                "title": title,
                "message": message,
                "related_document_id": document_id if change_type != "removed" else None,
                "is_read": False,
            }
            for u in eligible_users
            if u.get("user_id")
        ]

        try:
            self.supabase.table("notifications").insert(in_app_rows).execute()
            logger.info("Created %d in-app notification rows in database", len(in_app_rows))
        except Exception as exc:
            logger.error("Failed to insert in-app notifications: %s", exc)

        # 7. Dispatch transactional emails asynchronously (resilient to failure)
        email_count = 0
        for u in eligible_users:
            uid = str(u.get("user_id", ""))
            user_email = await self._resolve_user_email(uid)
            if not user_email:
                continue

            email_sent = await self._send_document_change_email(
                to_email=user_email,
                file_name=file_name,
                change_type=change_type,
            )
            if email_sent:
                email_count += 1

        logger.info(
            "Notification run complete: %d in-app notifications, %d emails dispatched",
            len(eligible_users), email_count,
        )

        return {
            "success": True,
            "notified_count": len(eligible_users),
            "emails_sent": email_count,
        }

    async def _resolve_user_email(self, user_id: str) -> Optional[str]:
        """Fetch user email securely using Supabase admin auth API."""
        try:
            user_res = self.supabase.auth.admin.get_user_by_id(user_id)
            if user_res and hasattr(user_res, "user") and user_res.user and user_res.user.email:
                return user_res.user.email
            if isinstance(user_res, dict) and "data" in user_res and user_res["data"]:
                return user_res["data"].get("email")
        except Exception as exc:
            logger.debug("Could not resolve email for user %s via admin auth: %s", user_id, exc)

        # Fallback: check raw user profiles or return None
        return None

    async def _send_document_change_email(
        self,
        to_email: str,
        file_name: str,
        change_type: str,
    ) -> bool:
        """Constructs and sends an enterprise-style transactional email."""
        subject_verb = "Added" if change_type == "added" else "Updated" if change_type == "updated" else "Removed"
        subject = f"Company Knowledge {subject_verb}: {file_name}"

        action_desc = (
            "has been added to Company Knowledge"
            if change_type == "added"
            else "has been updated"
            if change_type == "updated"
            else "has been removed from Company Knowledge"
        )
        instruction = (
            "You can open the Enterprise AI Assistant to review the document."
            if change_type != "removed"
            else "No further action is required."
        )

        body_text = (
            f"Hello,\n\n"
            f"A company document you have access to {action_desc}.\n\n"
            f"Document:\n{file_name}\n\n"
            f"Change:\nDocument {change_type}\n\n"
            f"{instruction}\n\n"
            f"Regards,\n"
            f"Enterprise AI Assistant"
        )

        body_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1e293b; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;">
            <div style="margin-bottom: 20px;">
                <span style="display: inline-block; padding: 4px 10px; font-size: 12px; font-weight: 600; color: #2563eb; background-color: #eff6ff; border-radius: 6px;">Enterprise Knowledge Update</span>
            </div>
            <h2 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #0f172a;">Company Document {subject_verb}</h2>
            <p style="font-size: 14px; line-height: 1.6; color: #475569; margin: 0 0 16px 0;">
                A company document you have access to {action_desc}.
            </p>
            <div style="padding: 16px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 20px;">
                <p style="margin: 0 0 6px 0; font-size: 13px; color: #64748b;"><strong>Document Name:</strong></p>
                <p style="margin: 0 0 12px 0; font-size: 15px; font-weight: 600; color: #0f172a;">{file_name}</p>
                <p style="margin: 0 0 4px 0; font-size: 13px; color: #64748b;"><strong>Status:</strong></p>
                <p style="margin: 0; font-size: 14px; color: #059669; font-weight: 500;">Document {change_type.capitalize()}</p>
            </div>
            <p style="font-size: 13px; line-height: 1.6; color: #64748b; margin: 0 0 24px 0;">
                {instruction}
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">
                Enterprise AI Assistant &bull; Automated notification
            </p>
        </div>
        """

        try:
            return await self.email_service.send_email(
                to_email=to_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
        except Exception as exc:
            logger.error("Email delivery failed for %s: %s (Ignored for safety)", to_email, exc)
            return False

    # ── User Preferences CRUD ──────────────────────────────────
    async def get_user_preference(self, user_id: str) -> Dict[str, Any]:
        try:
            res = (
                self.supabase.table("user_preferences")
                .select("user_id, company_file_updates, updated_at")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = cast(List[Dict[str, Any]], res.data or [])
            if rows:
                row = rows[0]
                return {
                    "user_id": user_id,
                    "company_file_updates": bool(row.get("company_file_updates", True)),
                    "updated_at": row.get("updated_at"),
                }
        except Exception as exc:
            logger.warning("Error reading user_preferences for %s: %s", user_id, exc)

        return {
            "user_id": user_id,
            "company_file_updates": True,
            "updated_at": None,
        }

    async def update_user_preference(
        self,
        user_id: str,
        company_file_updates: bool,
    ) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "user_id": user_id,
            "company_file_updates": company_file_updates,
            "updated_at": now_iso,
        }
        res = (
            self.supabase.table("user_preferences")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
        return {
            "user_id": user_id,
            "company_file_updates": company_file_updates,
            "updated_at": now_iso,
        }

    # ── Notifications Queries & Updates ───────────────────────
    async def get_user_notifications(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> Dict[str, Any]:
        query = (
            self.supabase.table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
        if unread_only:
            query = query.eq("is_read", False)

        query = query.range(offset, offset + limit - 1)
        res = query.execute()
        rows = cast(List[Dict[str, Any]], res.data or [])

        # Count unread
        unread_res = (
            self.supabase.table("notifications")
            .select("id")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )
        unread_rows = cast(List[Dict[str, Any]], unread_res.data or [])
        unread_count = len(unread_rows)

        return {
            "notifications": rows,
            "unread_count": unread_count,
            "total": len(rows),
        }

    async def mark_notification_as_read(
        self,
        user_id: str,
        notification_id: str,
    ) -> bool:
        self.supabase.table("notifications").update(
            {"is_read": True}
        ).eq("id", notification_id).eq("user_id", user_id).execute()
        return True

    async def mark_all_notifications_as_read(
        self,
        user_id: str,
    ) -> bool:
        self.supabase.table("notifications").update(
            {"is_read": True}
        ).eq("user_id", user_id).eq("is_read", False).execute()
        return True


_notification_service_instance: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _notification_service_instance
    if _notification_service_instance is None:
        _notification_service_instance = NotificationService()
    return _notification_service_instance
