"""Exercise real routes, authentication and SQLite, with external services stubbed."""
import ast
import asyncio
import hashlib
import hmac
import json
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'webapp/backend'))
import main
from database import HabitDB, MSK


class TrackerIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = HabitDB(str(Path(self.directory.name) / 'test.db'))
        await self.db.connect()
        self.addAsyncCleanup(self.db.close)
        # Use the actual bot table definitions without importing or starting the bot.
        for node in ast.parse((ROOT / 'app.py').read_text()).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {'DDL_USERS', 'DDL_PAYMENTS', 'DDL_CANCEL'} for t in node.targets):
                await self.db.conn.execute(ast.literal_eval(node.value))
        await self.db.init_schema()
        await self.db.conn.executemany('INSERT INTO users(user_id, expires_at) VALUES (?, ?)', [(42, int(time.time()) + 86400), (43, int(time.time()) + 86400), (44, 1), (99, 0)])
        await self.db.conn.commit()
        self.today = datetime.now(MSK).strftime('%Y-%m-%d')
        self.week = main.get_week_start(datetime.now(MSK))
        self.analysis = {'description': 'Курица с гречкой', 'products': ['Курица', 'Гречка'], 'categories': {'proteins': ['Курица'], 'carbs': ['Гречка']}}
        self.food_ai = AsyncMock(return_value=self.analysis)
        self.daily_ai = AsyncMock(return_value={'foods_list': ['Курица'], 'analysis': 'Тестовый итог'})
        self.weekly_ai = AsyncMock(return_value={'week_overview': 'Тестовый обзор', 'sleep_average': None})
        for replacement in [patch.object(main, 'db', self.db), patch.object(main, 'BOT_TOKEN', 'test-token'), patch.object(main, 'ADMIN_IDS_SET', {99}), patch.dict('os.environ', {'DEBUG': 'false'}), patch.object(main, 'analyze_food_text', self.food_ai), patch.object(main, 'analyze_food_photo', self.food_ai), patch.object(main, 'generate_daily_summary', self.daily_ai), patch.object(main, 'generate_weekly_summary', self.weekly_ai), patch.object(main, 'notify_admins', AsyncMock()), patch.object(main, 'send_telegram_message', AsyncMock(return_value=True)), patch.object(main, 'remove_user_from_group', AsyncMock(return_value=True))]:
            replacement.start()
            self.addCleanup(replacement.stop)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)

    def auth(self, uid=42, age=0):
        data = {'auth_date': str(int(time.time()) - age), 'user': json.dumps({'id': uid})}
        secret = hmac.new(b'WebAppData', b'test-token', hashlib.sha256).digest()
        data['hash'] = hmac.new(secret, '\n'.join(f'{k}={v}' for k, v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
        return {'X-Telegram-Init-Data': urlencode(data)}

    async def call(self, method, path, uid=42, **kwargs):
        return await self.client.request(method, '/api' + path, headers=self.auth(uid), **kwargs)

    async def food(self):
        response = await self.call('POST', '/food/text', json={'text': 'Курица с гречкой', 'time': '13:15', 'hunger_before': 2, 'ate_without_gadgets': True})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['entry_id']

    async def test_profile_settings_round_trip_and_owner_isolation(self):
        response = await self.call('POST', '/onboarding', json={'goal': 'maintain', 'training_type': 'own', 'activity_level': 'medium', 'gender': 'female', 'food_tracker_enabled': True})
        self.assertEqual(response.status_code, 200)
        await self.call('PATCH', '/settings', json={'morning_question_time': '09:30', 'sleep_tracker_enabled': True, 'user_id': 43})
        profile = (await self.call('GET', '/onboarding')).json()
        self.assertEqual(profile['morning_question_time'], '09:30')
        self.assertTrue(profile['onboarding_completed'])
        self.assertTrue(profile['sleep_tracker_enabled'])
        self.assertEqual((await self.call('GET', '/onboarding', uid=43)).json(), {})

    async def test_food_create_read_edit_calendar_and_delete(self):
        entry = await self.food()
        item = (await self.call('GET', '/food/today')).json()['entries'][0]
        self.assertEqual(item['time'], '13:15')
        self.assertEqual(item['categories'], self.analysis['categories'])
        self.assertTrue(item['ate_without_gadgets'])
        self.assertEqual((await self.call('PATCH', f'/food/{entry}', json={'description': 'Новый текст'})).status_code, 200)
        self.assertEqual((await self.call('PATCH', f'/food/{entry}/feelings', json={'fullness_after': 4})).status_code, 200)
        calendar = (await self.call('GET', f'/food/calendar/{datetime.now(MSK).year}/{datetime.now(MSK).month}')).json()
        self.assertEqual(calendar['days'][self.today]['entries'][0]['fullness_after'], 4)
        self.assertEqual((await self.call('DELETE', f'/food/{entry}')).status_code, 200)
        self.assertEqual((await self.call('GET', '/food/today')).json()['entries'], [])

    async def test_missing_and_other_users_food_never_reports_success(self):
        entry = await self.food()
        for uid, identifier in [(43, entry), (42, entry + 100)]:
            for method, path, payload in [('PATCH', f'/food/{identifier}', {'description': 'Чужая запись'}), ('PATCH', f'/food/{identifier}/feelings', {'hunger_before': 3}), ('DELETE', f'/food/{identifier}', None)]:
                with self.subTest(uid=uid, path=path):
                    kwargs = {'json': payload} if payload else {}
                    self.assertEqual((await self.call(method, path, uid=uid, **kwargs)).status_code, 404)
        self.assertEqual((await self.call('GET', '/food/today', uid=43)).json()['entries'], [])
        self.assertEqual((await self.call('GET', '/food/today')).json()['entries'][0]['description'], self.analysis['description'])

    async def test_photo_upload_analysis_and_failure_retry(self):
        self.food_ai.return_value = {'error': 'Provider unavailable'}
        failed = await self.call('POST', '/food/photo', files={'photo': ('meal.jpg', b'test-photo', 'image/jpeg')})
        self.assertEqual(failed.status_code, 503)
        self.assertEqual((await self.call('GET', '/food/today')).json()['entries'], [])
        self.food_ai.return_value = self.analysis
        success = await self.call('POST', '/food/photo', files={'photo': ('meal.jpg', b'test-photo', 'image/jpeg')}, data={'time': '12:30', 'context': 'Обед'})
        self.assertEqual(success.status_code, 200, success.text)
        self.assertEqual(len((await self.call('GET', '/food/today')).json()['entries']), 1)

    async def test_text_analysis_failure_does_not_silently_save_unanalyzed_food(self):
        self.food_ai.return_value = {'description': 'Raw text', 'error': 'Provider unavailable'}
        self.assertEqual((await self.call('POST', '/food/text', json={'text': 'Обед'})).status_code, 503)
        self.assertEqual((await self.call('GET', '/food/today')).json()['entries'], [])

    async def test_historical_food_entry_can_be_opened_only_by_owner(self):
        entry = await self.food()
        await self.db.conn.execute("UPDATE food_entries SET entry_date='2025-01-01' WHERE id=?", (entry,))
        await self.db.conn.commit()
        self.assertEqual((await self.call('GET', '/food/today')).json()['entries'], [])
        self.assertEqual((await self.call('GET', f'/food/entry/{entry}')).json()['entry']['id'], entry)
        self.assertEqual((await self.call('GET', f'/food/entry/{entry}', uid=43)).status_code, 404)

    async def test_sleep_replaces_same_day_and_rejects_invalid_score(self):
        for score in [2, 5]:
            self.assertEqual((await self.call('POST', '/sleep', json={'score': score})).status_code, 200)
        self.assertEqual((await self.call('GET', '/sleep/today')).json()['score'], 5)
        rows = await (await self.db.conn.execute('SELECT COUNT(*) FROM sleep_entries')).fetchone()
        self.assertEqual(rows[0], 1)
        self.assertIsNone((await self.call('GET', '/sleep/today', uid=43)).json()['score'])
        self.assertEqual((await self.call('POST', '/sleep', json={'score': 9})).status_code, 400)

    async def test_workout_create_read_delete_and_owner_isolation(self):
        result = await self.call('POST', '/workouts', json={'workout_name': 'Йога', 'duration_minutes': 30, 'intensity': 2})
        self.assertEqual(result.status_code, 200, result.text)
        identifier = result.json()['workout_id']
        self.assertEqual((await self.call('GET', f'/workouts/{self.today}')).json()['workouts'][0]['workout_name'], 'Йога')
        self.assertEqual((await self.call('DELETE', f'/workouts/{identifier}', uid=43)).status_code, 404)
        self.assertEqual((await self.call('DELETE', f'/workouts/{identifier}')).status_code, 200)

    async def test_summary_cache_is_reused_until_tracker_data_changes(self):
        await self.food()
        for _ in range(2):
            self.assertEqual((await self.call('GET', '/summary/today')).status_code, 200)
        self.daily_ai.assert_awaited_once()
        await self.call('POST', '/sleep', json={'score': 4})
        await self.call('GET', '/summary/today')
        self.assertEqual(self.daily_ai.await_count, 2)

    async def test_failed_summaries_can_be_retried_instead_of_cached_forever(self):
        await self.food()
        self.daily_ai.return_value = {'error': 'Unavailable', 'analysis': 'Failure'}
        self.assertEqual((await self.call('GET', '/summary/today')).status_code, 503)
        self.assertIsNone(await self.db.get_daily_summary(42, self.today))
        self.daily_ai.return_value = {'analysis': 'Recovered', 'foods_list': []}
        self.assertEqual((await self.call('GET', '/summary/today')).json()['summary']['analysis'], 'Recovered')

    async def test_old_cached_errors_are_ignored_without_deleting_valid_history(self):
        await self.db.conn.execute('INSERT INTO daily_summaries(user_id,summary_date,content) VALUES (?,?,?)', (42, self.today, '{"error":"old failure"}'))
        await self.db.conn.commit()
        self.assertIsNone(await self.db.get_daily_summary(42, self.today))
        await self.db.save_daily_summary(42, self.today, {'analysis': 'Valid'})
        await self.db.save_daily_summary(42, self.today, {'error': 'new failure'})
        self.assertEqual((await self.db.get_daily_summary(42, self.today))['analysis'], 'Valid')

    async def test_weekly_includes_workouts_only_and_invalidates_after_edit(self):
        await self.call('POST', '/workouts', json={'workout_name': 'Йога', 'duration_minutes': 30, 'intensity': 2})
        result = await self.call('GET', '/weekly/current')
        self.assertIsNotNone(result.json()['summary'])
        self.weekly_ai.assert_awaited_once()
        await self.food()
        await self.call('GET', '/weekly/current')
        self.assertEqual(self.weekly_ai.await_count, 2)

    async def test_empty_summary_does_not_call_provider(self):
        self.assertIsNone((await self.call('GET', '/summary/today')).json()['summary'])
        self.assertIsNone((await self.call('GET', '/weekly/current')).json()['summary'])
        self.daily_ai.assert_not_awaited()
        self.weekly_ai.assert_not_awaited()

    async def test_dashboard_achievements_and_streak_use_saved_data(self):
        await self.food()
        dashboard = (await self.call('GET', '/dashboard')).json()
        self.assertEqual(dashboard['food']['count'], 1)
        self.assertEqual(dashboard['streak']['current'], 1)
        self.assertEqual((await self.call('GET', '/achievements')).status_code, 200)

    async def test_expired_and_unauthenticated_users_cannot_access_trackers(self):
        for path in ['/onboarding', '/food/today', '/sleep/today', '/dashboard', '/summary/today', '/weekly/current', '/achievements']:
            with self.subTest(path=path):
                self.assertEqual((await self.call('GET', path, uid=44)).status_code, 403)
                self.assertEqual((await self.client.get('/api' + path)).status_code, 401)
                self.assertEqual((await self.client.get('/api' + path, headers=self.auth(age=90000))).status_code, 401)
        self.assertEqual((await self.call('POST', '/food/text', uid=44, json={'text': 'Test'})).status_code, 403)
        self.food_ai.assert_not_awaited()

    async def test_admin_sections_require_admin_and_work_without_subscription(self):
        for path in ['/admin/me', '/admin/stats', '/admin/operations', '/admin/console/summary', '/admin/users', '/admin/payments', '/admin/events', '/admin/users/42']:
            with self.subTest(path=path):
                self.assertEqual((await self.call('GET', path)).status_code, 403)
                result = await self.call('GET', path, uid=99)
                self.assertEqual(result.status_code, 200, result.text)

    async def test_auto_renewal_requires_card_and_unlink_keeps_paid_access(self):
        self.assertEqual((await self.call('POST', '/autorenewal/toggle')).status_code, 400)
        await self.db.set_payment_method(42, 'fake-test-card')
        self.assertTrue((await self.call('GET', '/autorenewal')).json()['enabled'])
        self.assertEqual((await self.call('POST', '/autorenewal/unlink')).status_code, 200)
        info = (await self.call('GET', '/autorenewal')).json()
        self.assertFalse(info['enabled'])
        self.assertFalse(info['has_payment_method'])
        self.assertEqual((await self.call('GET', '/me')).status_code, 200)

    async def test_same_payment_is_settled_once_across_independent_connections(self):
        await self.db.save_payment(44, 'shared-payment', 2590, 'pending')
        results = await asyncio.gather(*[self.db.settle_payment(44, 'shared-payment', 30, 1) for _ in range(3)])
        self.assertEqual(sum(r['applied'] for r in results), 1)
        self.assertEqual(len({r['expires_at'] for r in results}), 1)
        self.assertTrue(await self.db.is_subscription_active(44))
        self.assertEqual(await self.db.get_pending_payments(44), [])

    async def test_paid_renewal_preserves_remaining_days(self):
        before = (await (await self.db.conn.execute('SELECT expires_at FROM users WHERE user_id=42')).fetchone())[0]
        await self.db.save_payment(42, 'renewal-payment', 2590, 'pending')
        result = await self.db.settle_payment(42, 'renewal-payment', 30, 1)
        self.assertEqual(result['expires_at'], before + 31 * 86400)
        repeated = await self.db.settle_payment(42, 'renewal-payment', 30, 1)
        self.assertFalse(repeated['applied'])
        self.assertEqual(repeated['expires_at'], result['expires_at'])

    async def test_payment_ownership_is_checked_inside_transaction(self):
        await self.db.save_payment(42, 'owned-payment', 2590, 'pending')
        with self.assertRaises(ValueError):
            await self.db.settle_payment(44, 'owned-payment', 30, 1)
        self.assertFalse(await self.db.is_subscription_active(44))
        self.assertEqual(len(await self.db.get_pending_payments(42)), 1)

    async def test_stale_pending_response_cannot_make_a_settled_payment_retryable(self):
        await self.db.save_payment(44, 'stale-payment', 2590, 'pending')
        first = await self.db.settle_payment(44, 'stale-payment', 30, 1)
        await self.db.update_payment_status('stale-payment', 'pending')
        repeated = await self.db.settle_payment(44, 'stale-payment', 30, 1)
        self.assertFalse(repeated['applied'])
        self.assertEqual(repeated['expires_at'], first['expires_at'])

    async def test_repeated_payment_save_does_not_duplicate_revenue_or_reset_status(self):
        await self.db.save_payment(44, 'retry-save', 2590, 'pending')
        await self.db.settle_payment(44, 'retry-save', 30, 1)
        await self.db.save_payment(44, 'retry-save', 2590, 'pending')
        rows = await (await self.db.conn.execute('SELECT status FROM payments WHERE payment_id=?', ('retry-save',))).fetchall()
        self.assertEqual(rows, [('succeeded',)])

    async def test_payment_and_access_roll_back_together_on_database_failure(self):
        await self.db.save_payment(44, 'rollback-payment', 2590, 'pending')
        await self.db.conn.execute("CREATE TRIGGER fail_settlement BEFORE UPDATE ON payments BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
        await self.db.conn.commit()
        with self.assertRaises(Exception):
            await self.db.settle_payment(44, 'rollback-payment', 30, 1)
        self.assertFalse(await self.db.is_subscription_active(44))
        self.assertEqual(len(await self.db.get_pending_payments(44)), 1)
        await self.db.conn.execute('DROP TRIGGER fail_settlement')
        await self.db.conn.commit()
        self.assertTrue((await self.db.settle_payment(44, 'rollback-payment', 30, 1))['applied'])
