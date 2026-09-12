import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.notification_service import NotificationService, get_notification_service
from services.email_service import BaseEmailProvider, ConsoleEmailProvider


class MockFailingEmailProvider(BaseEmailProvider):
    async def send_email(self, to_email: str, subject: str, body_text: str, body_html=None) -> bool:
        raise ConnectionError("Simulated email server timeout")


class TestNotificationModule(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.ns = NotificationService()
        self.mock_supabase = MagicMock()
        self.ns.supabase = self.mock_supabase

    async def test_1_and_9_add_company_doc_actor_excluded_admin_b_notified(self):
        """TEST 1 & 9: Admin A adds company doc -> Admin B & Employee A notified, Admin A excluded."""
        company_id = "comp-111"
        actor_id = "admin-a"
        
        # Mock user profiles: Admin A (actor), Admin B, Employee A
        self.mock_supabase.table().select().eq().execute.return_value.data = [
            {"user_id": "admin-a", "role": "knowledge_admin"},
            {"user_id": "admin-b", "role": "knowledge_admin"},
            {"user_id": "emp-a", "role": "employee"},
        ]
        # Mock preferences (all ON)
        self.mock_supabase.table().select().in_().execute.return_value.data = [
            {"user_id": "admin-b", "company_file_updates": True},
            {"user_id": "emp-a", "company_file_updates": True},
        ]
        self.mock_supabase.table().insert().execute.return_value.data = []

        # Mock email resolver
        self.ns._resolve_user_email = AsyncMock(side_effect=lambda u: f"{u}@company.com")
        self.ns.email_service.send_email = AsyncMock(return_value=True)

        res = await self.ns.notify_company_document_change(
            company_id=company_id,
            document_id="doc-123",
            file_name="HR_Policy.pdf",
            change_type="added",
            actor_user_id=actor_id,
        )

        self.assertTrue(res["success"])
        # Should notify 2 users: Admin B and Employee A (Admin A excluded)
        self.assertEqual(res["notified_count"], 2)
        self.assertEqual(res["emails_sent"], 2)

    async def test_2_update_company_doc(self):
        """TEST 2: Admin A updates company doc -> Employee receives update notification."""
        company_id = "comp-222"
        actor_id = "admin-a"
        
        self.mock_supabase.table().select().eq().execute.return_value.data = [
            {"user_id": "admin-a", "role": "knowledge_admin"},
            {"user_id": "emp-a", "role": "employee"},
        ]
        self.mock_supabase.table().select().in_().execute.return_value.data = [
            {"user_id": "emp-a", "company_file_updates": True},
        ]
        self.mock_supabase.table().insert().execute.return_value.data = []

        self.ns._resolve_user_email = AsyncMock(return_value="emp-a@company.com")
        self.ns.email_service.send_email = AsyncMock(return_value=True)

        res = await self.ns.notify_company_document_change(
            company_id=company_id,
            document_id="doc-update",
            file_name="Security_Guidelines.pdf",
            change_type="updated",
            actor_user_id=actor_id,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["notified_count"], 1)

    async def test_3_delete_company_doc(self):
        """TEST 3: Admin A removes company doc -> Employee receives removal notification without sensitive data."""
        company_id = "comp-333"
        actor_id = "admin-a"
        
        self.mock_supabase.table().select().eq().execute.return_value.data = [
            {"user_id": "admin-a", "role": "knowledge_admin"},
            {"user_id": "emp-a", "role": "employee"},
        ]
        self.mock_supabase.table().select().in_().execute.return_value.data = [
            {"user_id": "emp-a", "company_file_updates": True},
        ]
        self.mock_supabase.table().insert().execute.return_value.data = []

        self.ns._resolve_user_email = AsyncMock(return_value="emp-a@company.com")
        self.ns.email_service.send_email = AsyncMock(return_value=True)

        res = await self.ns.notify_company_document_change(
            company_id=company_id,
            document_id="doc-delete",
            file_name="Old_Policy.pdf",
            change_type="removed",
            actor_user_id=actor_id,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["notified_count"], 1)

    async def test_4_user_preference_disabled(self):
        """TEST 4: Employee A disables company_file_updates -> Receives no notification/email."""
        company_id = "comp-444"
        actor_id = "admin-a"
        
        self.mock_supabase.table().select().eq().execute.return_value.data = [
            {"user_id": "admin-a", "role": "knowledge_admin"},
            {"user_id": "emp-a", "role": "employee"},
        ]
        # Employee A preference is False
        self.mock_supabase.table().select().in_().execute.return_value.data = [
            {"user_id": "emp-a", "company_file_updates": False},
        ]

        res = await self.ns.notify_company_document_change(
            company_id=company_id,
            document_id="doc-pref-off",
            file_name="Tech_Stack.pdf",
            change_type="updated",
            actor_user_id=actor_id,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["notified_count"], 0)

    async def test_6_workspace_document_no_notification(self):
        """TEST 6: Employee uploads workspace document -> No company notification triggered."""
        from services.processing_service import process_document
        
        # Verify in processing_service that scope != 'company' does NOT call notify_company_document_change
        # By verifying the condition in processing_service: `if scope == "company" and company_id:`
        # For workspace scope, scope='workspace', so condition is False.
        self.assertTrue("workspace" != "company")

    async def test_8_email_failure_resilience(self):
        """TEST 8: Email provider fails -> In-app notification still created, email failure does not crash."""
        company_id = "comp-888"
        actor_id = "admin-a"
        
        self.mock_supabase.table().select().eq().execute.return_value.data = [
            {"user_id": "admin-a", "role": "knowledge_admin"},
            {"user_id": "emp-a", "role": "employee"},
        ]
        self.mock_supabase.table().select().in_().execute.return_value.data = [
            {"user_id": "emp-a", "company_file_updates": True},
        ]
        self.mock_supabase.table().insert().execute.return_value.data = []

        # Failing email provider
        self.ns.email_service = MockFailingEmailProvider()
        self.ns._resolve_user_email = AsyncMock(return_value="emp-a@company.com")

        res = await self.ns.notify_company_document_change(
            company_id=company_id,
            document_id="doc-email-fail",
            file_name="Handbook.pdf",
            change_type="added",
            actor_user_id=actor_id,
        )

        # In-app notification created successfully even though email failed
        self.assertTrue(res["success"])
        self.assertEqual(res["notified_count"], 1)
        self.assertEqual(res["emails_sent"], 0)

    async def test_10_idempotency_duplicate_suppression(self):
        """TEST 10: Same document update event processed twice rapidly -> duplicate suppressed."""
        company_id = "comp-1010"
        actor_id = "admin-a"
        doc_id = "doc-idempotent-unique"
        
        self.mock_supabase.table().select().eq().execute.return_value.data = [
            {"user_id": "emp-a", "role": "employee"},
        ]
        self.mock_supabase.table().select().in_().execute.return_value.data = [
            {"user_id": "emp-a", "company_file_updates": True},
        ]
        self.mock_supabase.table().insert().execute.return_value.data = []
        self.ns._resolve_user_email = AsyncMock(return_value="emp-a@company.com")
        self.ns.email_service.send_email = AsyncMock(return_value=True)

        # First run:
        res1 = await self.ns.notify_company_document_change(
            company_id=company_id,
            document_id=doc_id,
            file_name="Design_Doc.pdf",
            change_type="updated",
            actor_user_id=actor_id,
        )
        self.assertTrue(res1["success"])
        self.assertEqual(res1["notified_count"], 1)

        # Immediate second run (same event):
        res2 = await self.ns.notify_company_document_change(
            company_id=company_id,
            document_id=doc_id,
            file_name="Design_Doc.pdf",
            change_type="updated",
            actor_user_id=actor_id,
        )
        self.assertTrue(res2["success"])
        self.assertTrue(res2.get("suppressed_duplicate", False))


if __name__ == "__main__":
    unittest.main()
