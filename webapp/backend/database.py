# webapp/backend/database.py
# Расширение схемы БД для habit tracker

import aiosqlite
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import json
import os

MSK = timezone(timedelta(hours=3))
DB_PATH = os.getenv("DB_PATH", "../../bot.db")

# DDL для новых таблиц
DDL_USER_PROFILES = """
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY,
    goal TEXT,                    -- 'maintain' | 'lose' | 'gain'
    training_type TEXT,           -- 'marathon' | 'own' | 'mixed'
    activity_level TEXT,          -- 'active' | 'medium' | 'calm'
    gender TEXT,                  -- 'male' | 'female'
    food_tracker_enabled INTEGER DEFAULT 0,
    sleep_tracker_enabled INTEGER DEFAULT 0,
    weekly_review_enabled INTEGER DEFAULT 0,
    evening_summary_time TEXT DEFAULT '21:00',
    morning_question_time TEXT DEFAULT '08:00',
    timezone_offset INTEGER DEFAULT 180,  -- offset в минутах от UTC (по умолчанию MSK +180)
    onboarding_completed INTEGER DEFAULT 0,
    created_at INTEGER,
    updated_at INTEGER
);
"""

DDL_FOOD_ENTRIES = """
CREATE TABLE IF NOT EXISTS food_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    entry_date TEXT,              -- '2025-01-18'
    entry_time TEXT,              -- '14:30'
    description TEXT,             -- распознанное описание
    photo_file_id TEXT,           -- Telegram file_id
    categories TEXT,              -- JSON: {"proteins": [...], "carbs": [...]}
    raw_input TEXT,               -- оригинальный текст пользователя
    source TEXT DEFAULT 'webapp', -- 'webapp' | 'telegram'
    hunger_before INTEGER,        -- 1-5: голод перед едой
    fullness_after INTEGER,       -- 1-5: сытость после еды (отмечать через 10-15 мин)
    ate_without_gadgets INTEGER DEFAULT 0,  -- 0 | 1: ел без гаджетов
    created_at INTEGER
);
"""

DDL_SLEEP_ENTRIES = """
CREATE TABLE IF NOT EXISTS sleep_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    entry_date TEXT,              -- '2025-01-18'
    score INTEGER,                -- 1-5
    created_at INTEGER,
    UNIQUE(user_id, entry_date)
);
"""

DDL_WORKOUT_ENTRIES = """
CREATE TABLE IF NOT EXISTS workout_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    entry_date TEXT,              -- '2025-01-18'
    workout_name TEXT,            -- название тренировки
    duration_minutes INTEGER,     -- длительность в минутах
    intensity INTEGER,            -- 1-5 (1=Light, 5=Intensive)
    created_at INTEGER
);
"""

DDL_DAILY_SUMMARIES = """
CREATE TABLE IF NOT EXISTS daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    summary_date TEXT,
    content TEXT,                 -- JSON с анализом
    sent_at INTEGER,
    UNIQUE(user_id, summary_date)
);
"""

DDL_WEEKLY_SUMMARIES = """
CREATE TABLE IF NOT EXISTS weekly_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    week_start TEXT,              -- '2025-01-13' (понедельник)
    content TEXT,                 -- JSON с анализом
    sent_at INTEGER,
    UNIQUE(user_id, week_start)
);
"""

DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_food_user_date ON food_entries(user_id, entry_date)",
    "CREATE INDEX IF NOT EXISTS idx_sleep_user_date ON sleep_entries(user_id, entry_date)",
    "CREATE INDEX IF NOT EXISTS idx_workout_user_date ON workout_entries(user_id, entry_date)",
    "CREATE INDEX IF NOT EXISTS idx_daily_user_date ON daily_summaries(user_id, summary_date)",
    "CREATE INDEX IF NOT EXISTS idx_weekly_user_week ON weekly_summaries(user_id, week_start)",
]


class HabitDB:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("PRAGMA foreign_keys=ON;")
        await self.conn.commit()

    async def init_schema(self):
        """Создаём таблицы для habit tracker"""
        assert self.conn is not None
        await self.conn.execute(DDL_USER_PROFILES)
        await self.conn.execute(DDL_FOOD_ENTRIES)
        await self.conn.execute(DDL_SLEEP_ENTRIES)
        await self.conn.execute(DDL_WORKOUT_ENTRIES)
        await self.conn.execute(DDL_DAILY_SUMMARIES)
        await self.conn.execute(DDL_WEEKLY_SUMMARIES)
        for idx in DDL_INDEXES:
            await self.conn.execute(idx)

        # Migrations for existing tables
        await self._run_migrations()

        await self.conn.commit()

    async def _run_migrations(self):
        """Run migrations to add new columns to existing tables"""
        # Get existing columns in user_profiles
        cur = await self.conn.execute("PRAGMA table_info(user_profiles)")
        columns = {row[1] for row in await cur.fetchall()}

        # Add gender column if missing
        if 'gender' not in columns:
            await self.conn.execute(
                "ALTER TABLE user_profiles ADD COLUMN gender TEXT"
            )

        # Get existing columns in food_entries
        cur = await self.conn.execute("PRAGMA table_info(food_entries)")
        columns = {row[1] for row in await cur.fetchall()}

        # Add ate_without_gadgets column if missing
        if 'ate_without_gadgets' not in columns:
            await self.conn.execute(
                "ALTER TABLE food_entries ADD COLUMN ate_without_gadgets INTEGER DEFAULT 0"
            )

    async def close(self):
        if self.conn:
            await self.conn.close()

    # ============ User Profiles (Onboarding) ============

    async def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        columns = [d[0] for d in cur.description]
        return dict(zip(columns, row))

    async def upsert_user_profile(self, user_id: int, data: Dict[str, Any]):
        now_ts = int(datetime.now(MSK).timestamp())
        existing = await self.get_user_profile(user_id)

        if existing:
            # Update
            fields = []
            values = []
            for key, value in data.items():
                if key != 'user_id':
                    fields.append(f"{key} = ?")
                    values.append(value)
            fields.append("updated_at = ?")
            values.append(now_ts)
            values.append(user_id)

            sql = f"UPDATE user_profiles SET {', '.join(fields)} WHERE user_id = ?"
            await self.conn.execute(sql, values)
        else:
            # Insert
            data['user_id'] = user_id
            data['created_at'] = now_ts
            data['updated_at'] = now_ts

            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            sql = f"INSERT INTO user_profiles ({columns}) VALUES ({placeholders})"
            await self.conn.execute(sql, list(data.values()))

        await self.conn.commit()

    async def is_subscription_active(self, user_id: int) -> bool:
        """Проверяем подписку в основной таблице users"""
        cur = await self.conn.execute(
            "SELECT expires_at FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        if not row or not row[0]:
            return False
        return row[0] > int(datetime.now(MSK).timestamp())

    # ============ Food Entries ============

    async def add_food_entry(
        self,
        user_id: int,
        description: str,
        photo_file_id: Optional[str] = None,
        categories: Optional[Dict] = None,
        raw_input: Optional[str] = None,
        source: str = 'webapp',
        custom_time: Optional[str] = None,  # Формат 'HH:MM'
        hunger_before: Optional[int] = None,  # 1-5
        fullness_after: Optional[int] = None,  # 1-5
        ate_without_gadgets: bool = False  # ел без гаджетов
    ) -> int:
        now = datetime.now(MSK)
        now_ts = int(now.timestamp())
        entry_date = now.strftime('%Y-%m-%d')
        entry_time = custom_time if custom_time else now.strftime('%H:%M')

        cur = await self.conn.execute(
            """
            INSERT INTO food_entries
            (user_id, entry_date, entry_time, description, photo_file_id, categories, raw_input, source, hunger_before, fullness_after, ate_without_gadgets, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                entry_date,
                entry_time,
                description,
                photo_file_id,
                json.dumps(categories) if categories else None,
                raw_input,
                source,
                hunger_before,
                fullness_after,
                1 if ate_without_gadgets else 0,
                now_ts
            )
        )
        await self.conn.commit()
        return cur.lastrowid

    async def update_food_entry_feelings(
        self,
        entry_id: int,
        user_id: int,
        hunger_before: Optional[int] = None,
        fullness_after: Optional[int] = None
    ) -> bool:
        """Обновить оценки голода и сытости для существующей записи"""
        updates = []
        params = []

        if hunger_before is not None:
            updates.append("hunger_before = ?")
            params.append(hunger_before)

        if fullness_after is not None:
            updates.append("fullness_after = ?")
            params.append(fullness_after)

        if not updates:
            return False

        params.extend([user_id, entry_id])

        await self.conn.execute(
            f"""
            UPDATE food_entries
            SET {', '.join(updates)}
            WHERE user_id = ? AND id = ?
            """,
            tuple(params)
        )
        await self.conn.commit()
        return True

    async def get_food_entries_for_date(
        self, user_id: int, date: str
    ) -> List[Dict[str, Any]]:
        cur = await self.conn.execute(
            """
            SELECT id, entry_time, description, photo_file_id, categories, raw_input, source, hunger_before, fullness_after, ate_without_gadgets
            FROM food_entries
            WHERE user_id = ? AND entry_date = ?
            ORDER BY entry_time ASC
            """,
            (user_id, date)
        )
        rows = await cur.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'time': row[1],
                'description': row[2],
                'photo_file_id': row[3],
                'categories': json.loads(row[4]) if row[4] else None,
                'raw_input': row[5],
                'source': row[6],
                'hunger_before': row[7],
                'fullness_after': row[8],
                'ate_without_gadgets': bool(row[9])
            })
        return result

    async def get_food_entries_for_week(
        self, user_id: int, week_start: str
    ) -> Dict[str, List[Dict]]:
        """Получить еду за неделю (week_start - понедельник)"""
        # Считаем 7 дней от понедельника
        from datetime import datetime as dt
        start = dt.strptime(week_start, '%Y-%m-%d')
        dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        result = {}
        for date in dates:
            result[date] = await self.get_food_entries_for_date(user_id, date)
        return result

    async def update_food_entry_description(
        self,
        entry_id: int,
        user_id: int,
        description: str
    ) -> bool:
        """Обновить описание приема пищи"""
        await self.conn.execute(
            """
            UPDATE food_entries
            SET description = ?
            WHERE user_id = ? AND id = ?
            """,
            (description, user_id, entry_id)
        )
        await self.conn.commit()
        return True

    async def delete_food_entry(self, user_id: int, entry_id: int) -> bool:
        cur = await self.conn.execute(
            "DELETE FROM food_entries WHERE id = ? AND user_id = ?",
            (entry_id, user_id)
        )
        await self.conn.commit()
        return cur.rowcount > 0

    # ============ Sleep Entries ============

    async def add_sleep_entry(self, user_id: int, score: int, date: Optional[str] = None) -> bool:
        now = datetime.now(MSK)
        now_ts = int(now.timestamp())
        entry_date = date or now.strftime('%Y-%m-%d')

        try:
            await self.conn.execute(
                """
                INSERT INTO sleep_entries (user_id, entry_date, score, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, entry_date) DO UPDATE SET score = excluded.score
                """,
                (user_id, entry_date, score, now_ts)
            )
            await self.conn.commit()
            return True
        except Exception:
            return False

    async def get_sleep_entry(self, user_id: int, date: str) -> Optional[int]:
        cur = await self.conn.execute(
            "SELECT score FROM sleep_entries WHERE user_id = ? AND entry_date = ?",
            (user_id, date)
        )
        row = await cur.fetchone()
        return row[0] if row else None

    async def get_sleep_entry_for_date(self, user_id: int, date: str) -> Optional[Dict[str, Any]]:
        """Получить запись о сне за конкретную дату (возвращает словарь)"""
        score = await self.get_sleep_entry(user_id, date)
        if score is not None:
            return {'score': score}
        return None

    async def get_sleep_entries_for_week(
        self, user_id: int, week_start: str
    ) -> Dict[str, Optional[int]]:
        from datetime import datetime as dt
        start = dt.strptime(week_start, '%Y-%m-%d')
        dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        result = {}
        for date in dates:
            result[date] = await self.get_sleep_entry(user_id, date)
        return result

    # ============ Workout Entries ============

    async def add_workout_entry(
        self,
        user_id: int,
        workout_name: str,
        duration_minutes: int,
        intensity: int,
        date: Optional[str] = None
    ) -> int:
        """Добавить тренировку"""
        now = datetime.now(MSK)
        now_ts = int(now.timestamp())
        entry_date = date or now.strftime('%Y-%m-%d')

        cur = await self.conn.execute(
            """
            INSERT INTO workout_entries
            (user_id, entry_date, workout_name, duration_minutes, intensity, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, entry_date, workout_name, duration_minutes, intensity, now_ts)
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_workout_entries_for_date(
        self, user_id: int, date: str
    ) -> List[Dict[str, Any]]:
        """Получить все тренировки за день"""
        cur = await self.conn.execute(
            """
            SELECT id, workout_name, duration_minutes, intensity
            FROM workout_entries
            WHERE user_id = ? AND entry_date = ?
            ORDER BY created_at ASC
            """,
            (user_id, date)
        )
        rows = await cur.fetchall()
        return [
            {
                'id': row[0],
                'workout_name': row[1],
                'duration_minutes': row[2],
                'intensity': row[3]
            }
            for row in rows
        ]

    async def delete_workout_entry(self, user_id: int, workout_id: int) -> bool:
        """Удалить тренировку"""
        cur = await self.conn.execute(
            "DELETE FROM workout_entries WHERE id = ? AND user_id = ?",
            (workout_id, user_id)
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def get_workout_entries_for_week(
        self, user_id: int, week_start: str
    ) -> Dict[str, List[Dict]]:
        """Получить тренировки за неделю (week_start - понедельник)"""
        from datetime import datetime as dt
        start = dt.strptime(week_start, '%Y-%m-%d')
        dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        result = {}
        for date in dates:
            result[date] = await self.get_workout_entries_for_date(user_id, date)
        return result

    # ============ Daily Summaries ============

    async def save_daily_summary(
        self, user_id: int, date: str, content: Dict[str, Any]
    ):
        now_ts = int(datetime.now(MSK).timestamp())
        await self.conn.execute(
            """
            INSERT INTO daily_summaries (user_id, summary_date, content, sent_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, summary_date) DO UPDATE SET
                content = excluded.content,
                sent_at = excluded.sent_at
            """,
            (user_id, date, json.dumps(content, ensure_ascii=False), now_ts)
        )
        await self.conn.commit()

    async def get_daily_summary(
        self, user_id: int, date: str
    ) -> Optional[Dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT content FROM daily_summaries WHERE user_id = ? AND summary_date = ?",
            (user_id, date)
        )
        row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    # ============ Weekly Summaries ============

    async def save_weekly_summary(
        self, user_id: int, week_start: str, content: Dict[str, Any]
    ):
        now_ts = int(datetime.now(MSK).timestamp())
        await self.conn.execute(
            """
            INSERT INTO weekly_summaries (user_id, week_start, content, sent_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, week_start) DO UPDATE SET
                content = excluded.content,
                sent_at = excluded.sent_at
            """,
            (user_id, week_start, json.dumps(content, ensure_ascii=False), now_ts)
        )
        await self.conn.commit()

    async def get_weekly_summary(
        self, user_id: int, week_start: str
    ) -> Optional[Dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT content FROM weekly_summaries WHERE user_id = ? AND week_start = ?",
            (user_id, week_start)
        )
        row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    # ============ Helpers ============

    async def get_users_for_notification(
        self, notification_type: str
    ) -> List[Dict[str, Any]]:
        """
        Получить пользователей для отправки уведомлений с их настройками времени и часового пояса
        notification_type: 'morning' | 'evening'
        Возвращает список dict с полями: user_id, notification_time, timezone_offset
        """
        if notification_type == 'morning':
            cur = await self.conn.execute(
                """
                SELECT up.user_id, up.morning_question_time, up.timezone_offset
                FROM user_profiles up
                JOIN users u ON up.user_id = u.user_id
                WHERE up.sleep_tracker_enabled = 1
                AND u.expires_at > ?
                """,
                (int(datetime.now(timezone.utc).timestamp()),)
            )
        else:  # evening
            cur = await self.conn.execute(
                """
                SELECT up.user_id, up.evening_summary_time, up.timezone_offset
                FROM user_profiles up
                JOIN users u ON up.user_id = u.user_id
                WHERE up.food_tracker_enabled = 1
                AND u.expires_at > ?
                """,
                (int(datetime.now(timezone.utc).timestamp()),)
            )

        rows = await cur.fetchall()
        return [
            {
                'user_id': row[0],
                'notification_time': row[1],
                'timezone_offset': row[2] or 180  # Default to MSK if null
            }
            for row in rows
        ]

    async def get_users_for_weekly_review(self) -> List[int]:
        """Получить пользователей с включённым недельным обзором и активной подпиской"""
        cur = await self.conn.execute(
            """
            SELECT up.user_id FROM user_profiles up
            JOIN users u ON up.user_id = u.user_id
            WHERE up.weekly_review_enabled = 1
            AND u.expires_at > ?
            """,
            (int(datetime.now(MSK).timestamp()),)
        )
        rows = await cur.fetchall()
        return [row[0] for row in rows]


# Singleton instance
db = HabitDB()
