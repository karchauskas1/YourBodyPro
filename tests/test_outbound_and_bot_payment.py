import ast
import asyncio
import logging
from functools import partial
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'webapp/backend'))
import http_client
import main
from payment_settlement import renewal_idempotency_key


class OutboundTransportTest(unittest.TestCase):
    def test_current_httpx_receives_configured_proxy(self):
        def factory(*, timeout, proxy=None):
            return {'timeout': timeout, 'proxy': proxy}
        with patch.dict('os.environ', {'OUTBOUND_PROXY_URL': 'socks5://127.0.0.1:1080'}), patch.object(http_client.httpx, 'AsyncClient', factory):
            self.assertEqual(http_client.outbound_client(timeout=30)['proxy'], 'socks5://127.0.0.1:1080')

    def test_deployed_httpx_receives_legacy_proxy_option(self):
        def factory(*, timeout, proxies=None):
            return {'timeout': timeout, 'proxy': proxies}
        with patch.dict('os.environ', {'OUTBOUND_PROXY_URL': 'socks5://127.0.0.1:1080'}), patch.object(http_client.httpx, 'AsyncClient', factory):
            self.assertEqual(http_client.outbound_client(timeout=10)['proxy'], 'socks5://127.0.0.1:1080')

    def test_no_proxy_is_required_for_local_tests(self):
        with patch.dict('os.environ', {'OUTBOUND_PROXY_URL': ''}), patch.object(http_client.httpx, 'AsyncClient') as factory:
            http_client.outbound_client(timeout=10)
            factory.assert_called_once_with(timeout=10)


class TelegramDeliveryTest(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_message_is_reported_without_reverting_access(self):
        database = SimpleNamespace(log_admin_event=AsyncMock())
        with patch.object(main, 'db', database), patch.object(main, 'create_one_time_invite_link', AsyncMock(return_value='https://t.me/test-invite')), patch.object(main, 'send_telegram_message', AsyncMock(return_value=False)), patch.object(main, 'notify_admins', AsyncMock()):
            result = await main.send_access_link_or_alert(42, 'test-payment')
            self.assertEqual(result, 'https://t.me/test-invite')
            self.assertEqual(database.log_admin_event.call_args.args[0], 'access_dm_failed')


class BotPaymentHandlerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Compile the actual handler without importing aiogram or starting bot services.
        node = next(n for n in ast.parse((ROOT / 'app.py').read_text()).body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'pay_check')
        node.decorator_list = []
        node.returns = None
        for argument in node.args.args:
            argument.annotation = None
        self.payment = SimpleNamespace(status='succeeded', metadata={'user_id': '42'})
        self.settle = AsyncMock(return_value={'applied': False, 'expires_at': 1800000000, 'was_active': True})
        self.reply = AsyncMock()
        self.db = SimpleNamespace(path='unused-test.db', get_user_phone=AsyncMock(return_value=None), update_payment_status=AsyncMock())
        namespace = {'asyncio': asyncio, 'Payment': SimpleNamespace(find_one=Mock(side_effect=lambda _: self.payment)), 'db': self.db,
                     'replace_with_text': self.reply, 'settle_payment': self.settle, 'PAID_DAYS': 30, 'GRACE_DAYS': 1,
                     'log': logging.getLogger('bot-payment-test'), 'kb': lambda x: x, 'kb_row': lambda x: x, 'InlineKeyboardButton': lambda **x: x}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / 'app.py'), 'exec'), namespace)
        self.handler = namespace['pay_check']
        self.callback = SimpleNamespace(data='pay_check:test-payment', answer=AsyncMock(), from_user=SimpleNamespace(id=42))

    async def test_bot_rejects_payment_for_a_different_account(self):
        self.payment.metadata['user_id'] = '99'
        await self.handler(self.callback)
        self.settle.assert_not_awaited()
        self.db.update_payment_status.assert_not_awaited()

    async def test_bot_rechecking_settled_payment_does_not_redeliver_or_extend(self):
        await self.handler(self.callback)
        self.settle.assert_awaited_once_with('unused-test.db', 42, 'test-payment', 30, 1)
        self.assertIn('уже учтён', self.reply.call_args.args[1])

    async def test_bot_database_failure_keeps_a_visible_retry(self):
        self.settle.side_effect = RuntimeError('temporary failure')
        await self.handler(self.callback)
        self.assertIn('Повторно оплачивать не нужно', self.reply.call_args.args[1])
        self.db.update_payment_status.assert_not_awaited()


class AutoRenewalTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        node = next(n for n in ast.parse((ROOT / 'app.py').read_text()).body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'auto_renewal_job')
        self.user = {'user_id': 42, 'expires_at': 1800000000, 'payment_method_id': 'test-card'}
        self.payment = SimpleNamespace(id='renewal-test', status='succeeded')
        self.create = Mock(side_effect=lambda *args, **kwargs: self.payment)
        self.settle = AsyncMock(return_value={'applied': True, 'expires_at': 1801000000})
        self.bot = SimpleNamespace(send_message=AsyncMock())
        self.db = SimpleNamespace(path='unused-test.db', get_users_for_auto_renewal=AsyncMock(return_value=[self.user]), get_user_phone=AsyncMock(return_value=None), save_payment=AsyncMock(), reset_auto_renewal_failures=AsyncMock(), increment_auto_renewal_failures=AsyncMock(), log_admin_event=AsyncMock(), get_auto_renewal_info=AsyncMock(return_value={'failures': 1}))
        async def stop_after_iteration(*args):
            raise asyncio.CancelledError()
        namespace = {'asyncio': SimpleNamespace(wait_for=asyncio.wait_for, to_thread=asyncio.to_thread, sleep=stop_after_iteration),
                     'db': self.db, 'bot': self.bot, 'Payment': SimpleNamespace(create=self.create), 'partial': partial,
                     'settle_payment': self.settle, 'renewal_idempotency_key': renewal_idempotency_key,
                     'MONTH_PRICE': 2590, 'PAID_DAYS': 30, 'GRACE_DAYS': 1, 'AUTO_RENEWAL_INTERVAL': 21600,
                     'log': logging.getLogger('renewal-test')}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / 'app.py'), 'exec'), namespace)
        self.job = namespace['auto_renewal_job']

    async def run_iteration(self):
        with self.assertRaises(asyncio.CancelledError):
            await self.job()

    async def test_retry_after_lost_response_reuses_provider_idempotency_key(self):
        self.create.side_effect = [TimeoutError('response lost'), self.payment]
        await self.run_iteration()
        await self.run_iteration()
        self.assertEqual(self.create.call_args_list[0].kwargs['idempotency_key'], self.create.call_args_list[1].kwargs['idempotency_key'])
        self.settle.assert_awaited_once()

    async def test_pending_renewal_is_saved_without_disabling_the_card(self):
        self.payment.status = 'pending'
        await self.run_iteration()
        self.db.save_payment.assert_awaited_once_with(42, 'renewal-test', 2590, 'pending')
        self.db.increment_auto_renewal_failures.assert_not_awaited()
        self.settle.assert_not_awaited()

    async def test_new_subscription_period_uses_a_new_provider_key(self):
        await self.run_iteration()
        self.user['expires_at'] += 31 * 86400
        await self.run_iteration()
        self.assertNotEqual(self.create.call_args_list[0].kwargs['idempotency_key'], self.create.call_args_list[1].kwargs['idempotency_key'])

    async def test_already_applied_renewal_does_not_send_duplicate_success(self):
        self.settle.return_value['applied'] = False
        await self.run_iteration()
        self.bot.send_message.assert_not_awaited()

