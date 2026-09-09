import sys
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import requests
from fastapi import BackgroundTasks, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp" / "backend"))
import main


class PaymentAccessTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(
            is_subscription_active=AsyncMock(return_value=False),
            get_pending_payments=AsyncMock(return_value=[]),
            update_payment_status=AsyncMock(),
            activate_subscription=AsyncMock(return_value=1800000000),
            mark_referral_paid=AsyncMock(return_value=None),
            log_admin_event=AsyncMock(),
        )
        self.db_patch = patch.object(main, "db", self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.request_patch = patch("requests.get")
        self.request = self.request_patch.start()
        self.addCleanup(self.request_patch.stop)

    def pending_payment(self, status="succeeded", owner=42):
        self.db.get_pending_payments.return_value = [{"payment_id": "payment-test"}]
        self.request.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "id": "payment-test", "status": status,
                "metadata": {"user_id": str(owner)},
            }),
        )

    async def test_completed_payment_still_confirms_existing_access(self):
        self.db.is_subscription_active.return_value = True
        tasks = BackgroundTasks()
        result = await main.check_payment(tasks, {"user_id": 42})
        self.assertTrue(result["subscription_active"])
        self.request.assert_not_called()
        self.db.activate_subscription.assert_not_awaited()
        self.assertEqual(tasks.tasks, [])

    async def test_unpaid_user_is_not_granted_access(self):
        result = await main.check_payment(BackgroundTasks(), {"user_id": 42})
        self.assertFalse(result["subscription_active"])
        self.db.activate_subscription.assert_not_awaited()

    async def test_activation_failure_leaves_payment_retryable(self):
        self.pending_payment()
        self.db.activate_subscription.side_effect = RuntimeError("Database unavailable")
        with self.assertRaises(RuntimeError):
            await main.check_payment(BackgroundTasks(), {"user_id": 42})
        self.db.update_payment_status.assert_not_awaited()

    async def test_repeated_check_does_not_activate_or_deliver_twice(self):
        self.pending_payment()
        async def mark_paid(payment_id, status):
            if status == "succeeded":
                self.db.is_subscription_active.return_value = True
                self.db.get_pending_payments.return_value = []
        self.db.update_payment_status.side_effect = mark_paid
        first, second = BackgroundTasks(), BackgroundTasks()
        self.assertTrue((await main.check_payment(first, {"user_id": 42}))["subscription_active"])
        self.assertTrue((await main.check_payment(second, {"user_id": 42}))["subscription_active"])
        self.db.activate_subscription.assert_awaited_once()
        self.request.assert_called_once()
        self.assertEqual(len(first.tasks), 1)
        self.assertEqual(second.tasks, [])

    async def test_simultaneous_checks_activate_and_schedule_delivery_once(self):
        self.pending_payment()
        async def activate(*args):
            await asyncio.sleep(0.01)
            self.db.is_subscription_active.return_value = True
            return 1800000000
        async def mark_paid(payment_id, status):
            if status == "succeeded":
                self.db.get_pending_payments.return_value = []
        self.db.activate_subscription.side_effect = activate
        self.db.update_payment_status.side_effect = mark_paid
        first, second = BackgroundTasks(), BackgroundTasks()
        results = await asyncio.gather(
            main.check_payment(first, {"user_id": 42}),
            main.check_payment(second, {"user_id": 42}),
        )
        self.assertTrue(all(result["subscription_active"] for result in results))
        self.db.activate_subscription.assert_awaited_once()
        self.request.assert_called_once()
        self.assertEqual(len(first.tasks) + len(second.tasks), 1)

    async def test_payment_provider_timeout_does_not_grant_or_consume_payment(self):
        self.pending_payment()
        self.request.side_effect = requests.Timeout("Payment provider unavailable")
        with self.assertRaises(HTTPException) as error:
            await main.check_payment(BackgroundTasks(), {"user_id": 42})
        self.assertEqual(error.exception.status_code, 500)
        self.db.activate_subscription.assert_not_awaited()
        self.db.update_payment_status.assert_not_awaited()

    async def test_payment_provider_error_does_not_grant_access(self):
        self.pending_payment()
        self.request.return_value.status_code = 503
        self.request.return_value.text = "Unavailable"
        with self.assertRaises(HTTPException):
            await main.check_payment(BackgroundTasks(), {"user_id": 42})
        self.db.activate_subscription.assert_not_awaited()
        self.db.update_payment_status.assert_not_awaited()

    async def test_canceled_and_pending_payments_never_grant_access(self):
        for status in ["pending", "canceled", "waiting_for_capture"]:
            with self.subTest(status=status):
                self.pending_payment(status=status)
                result = await main.check_payment(BackgroundTasks(), {"user_id": 42})
                self.assertFalse(result["subscription_active"])
                self.db.activate_subscription.assert_not_awaited()

    async def test_active_user_can_still_confirm_new_payment(self):
        self.db.is_subscription_active.return_value = True
        self.pending_payment()
        tasks = BackgroundTasks()
        result = await main.check_payment(tasks, {"user_id": 42})
        self.assertEqual(result["payment_id"], "payment-test")
        self.request.assert_called_once()
        self.db.activate_subscription.assert_awaited_once()
        self.assertEqual(tasks.tasks, [])

    async def test_old_pending_payment_does_not_hide_active_subscription(self):
        self.db.is_subscription_active.return_value = True
        self.pending_payment(status="pending")
        result = await main.check_payment(BackgroundTasks(), {"user_id": 42})
        self.assertTrue(result["subscription_active"])
        self.db.activate_subscription.assert_not_awaited()

    async def test_telegram_timeout_does_not_fail_successful_payment(self):
        self.pending_payment()
        tasks = BackgroundTasks()
        with patch.object(main, "create_one_time_invite_link", AsyncMock(
            side_effect=httpx.ConnectTimeout("Telegram unavailable")
        )) as invite, patch.object(main, "notify_admins", AsyncMock()) as notify:
            result = await main.check_payment(tasks, {"user_id": 42})
            self.assertTrue(result["subscription_active"])
            self.assertEqual(result["expires_at"], 1800000000)
            invite.assert_not_awaited()
            self.db.activate_subscription.assert_awaited_once()
            self.assertEqual(len(tasks.tasks), 1)
            await tasks()
            self.db.log_admin_event.assert_awaited_once()
            self.assertEqual(self.db.log_admin_event.call_args.args[0], "invite_link_failed")
            notify.assert_awaited_once()

    async def test_payment_for_another_user_never_grants_access(self):
        self.pending_payment(owner=99)
        result = await main.check_payment(BackgroundTasks(), {"user_id": 42})
        self.assertFalse(result["subscription_active"])
        self.db.activate_subscription.assert_not_awaited()

    async def test_authentication_is_required(self):
        with self.assertRaises(HTTPException) as error:
            await main.check_payment(BackgroundTasks(), None)
        self.assertEqual(error.exception.status_code, 401)
        self.db.is_subscription_active.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
