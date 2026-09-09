"""Refresh synthetic browser responses from real routes and an isolated SQLite DB."""
import json
import unittest
from pathlib import Path

from test_tracker_integration import TrackerIntegrationTest


class ExportBrowserFixtures(TrackerIntegrationTest):
    async def export(self):
        await self.call('POST', '/onboarding', json={
            'goal': 'maintain', 'training_type': 'own', 'activity_level': 'medium',
            'gender': 'female', 'food_tracker_enabled': True, 'sleep_tracker_enabled': True,
            'weekly_review_enabled': True,
        })
        await self.food()
        self.daily_ai.return_value = {'foods_list': ['Курица', 'Гречка'], 'analysis': 'Тестовый итог дня', 'balance_note': 'Разнообразный рацион', 'suggestion': None}
        self.weekly_ai.return_value = {'week_overview': 'Тестовый обзор недели', 'food_diversity_by_day': {}, 'sleep_average': 4, 'sleep_food_patterns': [], 'timing_patterns': [], 'balance_insights': []}
        data = {}
        for path in ['/me', '/dashboard', '/onboarding', '/food/today', '/food/entry/1', '/sleep/today', '/summary/today', '/weekly/current', '/autorenewal', '/referral', '/achievements', '/streak',
                     f'/food/calendar/{self.today[:4]}/{int(self.today[5:7])}',
                     '/admin/me', '/admin/stats', '/admin/operations', '/admin/console/summary', '/admin/users', '/admin/users/42', '/admin/payments', '/admin/events']:
            response = await self.call('GET', path, uid=99 if path.startswith('/admin') else 42)
            self.assertEqual(response.status_code, 200, response.text)
            key = '/food/calendar' if path.startswith('/food/calendar/') else path
            data[key] = response.json()
        destination = Path(__file__).resolve().parents[1] / 'webapp/frontend/tests/fixtures/api-responses.json'
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    result = unittest.TextTestRunner().run(ExportBrowserFixtures('export'))
    raise SystemExit(0 if result.wasSuccessful() else 1)
