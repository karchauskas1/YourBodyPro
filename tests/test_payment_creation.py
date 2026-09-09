import asyncio
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import requests
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp/backend'))
import main


class PaymentCreationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(get_user_phone=AsyncMock(return_value=None), get_unused_referral_reward=AsyncMock(return_value={'id': 1, 'discount_percent': 30}), save_payment=AsyncMock(), use_referral_reward=AsyncMock())
        replacement = patch.object(main, 'db', self.db)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.response = Mock(status_code=200, json=Mock(return_value={'id': 'new-payment', 'status': 'pending', 'confirmation': {'confirmation_url': 'https://example.test/pay'}}))

    async def test_provider_failure_does_not_consume_referral_discount(self):
        with patch('requests.post', side_effect=requests.Timeout('Provider unavailable')):
            with self.assertRaises(HTTPException):
                await main.create_payment({'user_id': 42})
        self.db.save_payment.assert_not_awaited()
        self.db.use_referral_reward.assert_not_awaited()

    async def test_payment_is_saved_before_consuming_discount(self):
        async def consume(_):
            self.db.save_payment.assert_awaited_once()
        self.db.use_referral_reward.side_effect = consume
        with patch('requests.post', return_value=self.response) as provider:
            result = await main.create_payment({'user_id': 42})
        self.assertEqual(result['payment_id'], 'new-payment')
        self.assertEqual(provider.call_args.kwargs['json']['metadata']['user_id'], '42')
        self.db.use_referral_reward.assert_awaited_once_with(1)

    async def test_slow_provider_does_not_block_other_api_work(self):
        started, release = threading.Event(), threading.Event()
        def provider(*args, **kwargs):
            started.set()
            release.wait(1)
            return self.response
        with patch('requests.post', side_effect=provider):
            task = asyncio.create_task(main.create_payment({'user_id': 42}))
            try:
                await asyncio.to_thread(started.wait, 2)
                self.assertFalse(task.done(), 'Provider request blocked the API event loop')
                self.assertEqual((await main.health_check())['status'], 'ok')
            finally:
                release.set()
                await task
