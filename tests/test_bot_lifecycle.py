import ast
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiosqlite

ROOT = Path(__file__).resolve().parents[1]


def compile_function(path, name, namespace):
    node = next(n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    node.decorator_list = []
    for argument in node.args.args:
        argument.annotation = None
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class BotLifecycleTest(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_cancels_workers_and_closes_both_sqlite_connections(self):
        bot_connection = await aiosqlite.connect(':memory:')
        habit_connection = await aiosqlite.connect(':memory:')
        self.addAsyncCleanup(bot_connection.close)
        self.addAsyncCleanup(habit_connection.close)
        tasks = [asyncio.create_task(asyncio.Event().wait()) for _ in range(2)]
        owned_tasks = list(tasks)
        shutdown = compile_function(ROOT / 'app.py', 'on_shutdown', {
            'asyncio': asyncio, '_background_tasks': owned_tasks, 'HABIT_TRACKER_ENABLED': True,
            'db': SimpleNamespace(conn=bot_connection),
        })
        with patch.dict(sys.modules, {'habit_handlers': SimpleNamespace(habit_db=SimpleNamespace(close=habit_connection.close))}):
            await asyncio.wait_for(shutdown(), timeout=1)
        self.assertTrue(all(task.cancelled() for task in tasks))
        self.assertEqual(owned_tasks, [])
        for connection in [bot_connection, habit_connection]:
            with self.assertRaises(ValueError):
                await connection.execute('SELECT 1')

    async def habits(self, active):
        database = SimpleNamespace(get_user=AsyncMock(return_value=SimpleNamespace(expires_at=1) if active else None))
        handler = compile_function(ROOT / 'habit_handlers.py', 'habits_command', {
            'main_db': database, 'is_active': lambda expires: expires > 0,
            'webapp_url': lambda: 'https://example.test/app',
            'InlineKeyboardMarkup': lambda **kwargs: kwargs, 'InlineKeyboardButton': lambda **kwargs: kwargs,
        })
        message = SimpleNamespace(from_user=SimpleNamespace(id=42), answer=AsyncMock())
        await handler(message)
        database.get_user.assert_awaited_once_with(42)
        return message.answer

    async def test_habits_command_uses_the_running_bots_database(self):
        answer = await self.habits(True)
        self.assertEqual(answer.call_args.kwargs['reply_markup']['inline_keyboard'][0][0]['web_app']['url'], 'https://example.test/app')

    async def test_habits_command_does_not_open_access_for_unpaid_user(self):
        answer = await self.habits(False)
        self.assertNotIn('reply_markup', answer.call_args.kwargs)
        self.assertIn('активной подпиской', answer.call_args.args[0])
