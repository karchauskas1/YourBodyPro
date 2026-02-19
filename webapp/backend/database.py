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

DDL_REFERRALS = """
CREATE TABLE IF NOT EXISTS referrals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id INTEGER NOT NULL,
    referred_id INTEGER NOT NULL,
    referred_paid INTEGER DEFAULT 0,
    reward_granted INTEGER DEFAULT 0,
    created_at  INTEGER,
    UNIQUE(referred_id)
);
"""

DDL_REFERRAL_REWARDS = """
CREATE TABLE IF NOT EXISTS referral_rewards (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    discount_percent INTEGER DEFAULT 30,
    used            INTEGER DEFAULT 0,
    created_at      INTEGER
);
"""

DDL_USER_ACHIEVEMENTS = """
CREATE TABLE IF NOT EXISTS user_achievements (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    achievement_id TEXT NOT NULL,
    unlocked_at    INTEGER,
    UNIQUE(user_id, achievement_id)
);
"""

DDL_BROADCAST_LOG = """
CREATE TABLE IF NOT EXISTS broadcast_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id      INTEGER NOT NULL,
    segment       TEXT NOT NULL,
    message_text  TEXT NOT NULL,
    sent_count    INTEGER DEFAULT 0,
    failed_count  INTEGER DEFAULT 0,
    blocked_count INTEGER DEFAULT 0,
    created_at    INTEGER
);
"""

DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_food_user_date ON food_entries(user_id, entry_date)",
    "CREATE INDEX IF NOT EXISTS idx_sleep_user_date ON sleep_entries(user_id, entry_date)",
    "CREATE INDEX IF NOT EXISTS idx_workout_user_date ON workout_entries(user_id, entry_date)",
    "CREATE INDEX IF NOT EXISTS idx_daily_user_date ON daily_summaries(user_id, summary_date)",
    "CREATE INDEX IF NOT EXISTS idx_weekly_user_week ON weekly_summaries(user_id, week_start)",
    "CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)",
    "CREATE INDEX IF NOT EXISTS idx_referral_rewards_user ON referral_rewards(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)",
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
        await self.conn.execute(DDL_REFERRALS)
        await self.conn.execute(DDL_REFERRAL_REWARDS)
        await self.conn.execute(DDL_USER_ACHIEVEMENTS)
        await self.conn.execute(DDL_BROADCAST_LOG)
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

        # --- Auto-renewal & referral migrations for users table ---
        cur = await self.conn.execute("PRAGMA table_info(users)")
        user_columns = {row[1] for row in await cur.fetchall()}
        for col, definition in [
            ('payment_method_id', 'TEXT'),
            ('auto_renewal', 'INTEGER DEFAULT 0'),
            ('auto_renewal_agreed_at', 'INTEGER'),
            ('auto_renewal_failures', 'INTEGER DEFAULT 0'),
            ('referral_code', 'TEXT'),
        ]:
            if col not in user_columns:
                await self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")

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


    async def get_user_phone(self, user_id: int) -> Optional[str]:
        """Получить телефон пользователя"""
        cur = await self.conn.execute(
            "SELECT phone FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row and row[0] else None

    async def activate_subscription(self, user_id: int, paid_days: int, grace_days: int):
        """Активировать подписку для пользователя"""
        now_ts = int(datetime.now(MSK).timestamp())
        desired_expires = now_ts + (paid_days + grace_days) * 86400

        # Берём текущий expires_at чтобы не уменьшить
        cur = await self.conn.execute(
            "SELECT expires_at FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        existing_expires = row[0] if row and row[0] else 0

        new_expires = max(desired_expires, existing_expires)

        await self.conn.execute(
            "UPDATE users SET expires_at = ? WHERE user_id = ?",
            (new_expires, user_id)
        )
        await self.conn.commit()
        return new_expires

    async def save_payment(self, user_id: int, payment_id: str, amount: int, status: str):
        """Сохранить платёж в таблицу payments"""
        now_ts = int(datetime.now(MSK).timestamp())
        await self.conn.execute(
            """INSERT OR REPLACE INTO payments (user_id, payment_id, amount, status, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, payment_id, amount, status, now_ts)
        )
        await self.conn.commit()

    async def update_payment_status(self, payment_id: str, status: str):
        """Обновить статус платежа"""
        await self.conn.execute(
            "UPDATE payments SET status = ? WHERE payment_id = ?",
            (status, payment_id)
        )
        await self.conn.commit()

    # ============ Auto-Renewal ============

    async def set_payment_method(self, user_id: int, payment_method_id: str):
        await self.conn.execute(
            "UPDATE users SET payment_method_id=? WHERE user_id=?",
            (payment_method_id, user_id)
        )
        await self.conn.commit()

    async def set_auto_renewal(self, user_id: int, enabled: bool, agreed_at: int = None):
        if enabled and agreed_at:
            await self.conn.execute(
                "UPDATE users SET auto_renewal=1, auto_renewal_agreed_at=?, auto_renewal_failures=0 WHERE user_id=?",
                (agreed_at, user_id)
            )
        else:
            await self.conn.execute(
                "UPDATE users SET auto_renewal=0 WHERE user_id=?",
                (user_id,)
            )
        await self.conn.commit()

    async def get_auto_renewal_info(self, user_id: int) -> Optional[Dict]:
        cur = await self.conn.execute(
            "SELECT payment_method_id, auto_renewal, auto_renewal_agreed_at, auto_renewal_failures FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "payment_method_id": row[0],
            "auto_renewal": bool(row[1]),
            "auto_renewal_agreed_at": row[2],
            "auto_renewal_failures": row[3] or 0,
        }

    async def clear_payment_method(self, user_id: int):
        await self.conn.execute(
            "UPDATE users SET payment_method_id=NULL, auto_renewal=0, auto_renewal_failures=0 WHERE user_id=?",
            (user_id,)
        )
        await self.conn.commit()

    # ============ Referrals ============

    async def get_referral_code(self, user_id: int) -> Optional[str]:
        cur = await self.conn.execute(
            "SELECT referral_code FROM users WHERE user_id=?", (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row and row[0] else None

    async def set_referral_code(self, user_id: int, code: str):
        await self.conn.execute(
            "UPDATE users SET referral_code=? WHERE user_id=?", (code, user_id)
        )
        await self.conn.commit()

    async def find_user_by_referral_code(self, code: str) -> Optional[int]:
        cur = await self.conn.execute(
            "SELECT user_id FROM users WHERE UPPER(referral_code)=UPPER(?)", (code,)
        )
        row = await cur.fetchone()
        return row[0] if row else None

    async def create_referral(self, referrer_id: int, referred_id: int):
        now_ts = int(datetime.now(MSK).timestamp())
        try:
            await self.conn.execute(
                "INSERT OR IGNORE INTO referrals (referrer_id, referred_id, created_at) VALUES (?,?,?)",
                (referrer_id, referred_id, now_ts)
            )
            await self.conn.commit()
        except Exception:
            pass

    async def get_referral_for_user(self, referred_id: int) -> Optional[Dict]:
        cur = await self.conn.execute(
            "SELECT referrer_id, referred_paid, reward_granted FROM referrals WHERE referred_id=?",
            (referred_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {"referrer_id": row[0], "referred_paid": bool(row[1]), "reward_granted": bool(row[2])}

    async def mark_referral_paid(self, referred_id: int) -> Optional[int]:
        """Mark referral as paid, create reward for referrer. Returns referrer_id or None."""
        cur = await self.conn.execute(
            "SELECT referrer_id FROM referrals WHERE referred_id=? AND referred_paid=0",
            (referred_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        referrer_id = row[0]
        now_ts = int(datetime.now(MSK).timestamp())
        await self.conn.execute(
            "UPDATE referrals SET referred_paid=1, reward_granted=1 WHERE referred_id=?",
            (referred_id,)
        )
        await self.conn.execute(
            "INSERT INTO referral_rewards (user_id, discount_percent, used, created_at) VALUES (?,30,0,?)",
            (referrer_id, now_ts)
        )
        await self.conn.commit()
        return referrer_id

    async def get_unused_referral_reward(self, user_id: int) -> Optional[Dict]:
        cur = await self.conn.execute(
            "SELECT id, discount_percent FROM referral_rewards WHERE user_id=? AND used=0 ORDER BY created_at ASC LIMIT 1",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "discount_percent": row[1]}

    async def use_referral_reward(self, reward_id: int):
        await self.conn.execute(
            "UPDATE referral_rewards SET used=1 WHERE id=?", (reward_id,)
        )
        await self.conn.commit()

    async def get_referral_stats(self, user_id: int) -> Dict:
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,)
        )
        total = (await cur.fetchone())[0]
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND referred_paid=1", (user_id,)
        )
        paid = (await cur.fetchone())[0]
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM referral_rewards WHERE user_id=? AND used=0", (user_id,)
        )
        available_rewards = (await cur.fetchone())[0]
        return {"total_invited": total, "total_paid": paid, "available_rewards": available_rewards}

    # ============ Streaks ============

    async def get_food_streak(self, user_id: int) -> Dict[str, int]:
        """Calculate current and best food logging streak."""
        cur = await self.conn.execute(
            "SELECT DISTINCT entry_date FROM food_entries WHERE user_id=? ORDER BY entry_date DESC",
            (user_id,)
        )
        rows = await cur.fetchall()
        if not rows:
            return {"current": 0, "best": 0}

        dates = [row[0] for row in rows]
        today = datetime.now(MSK).strftime('%Y-%m-%d')

        # Current streak: count consecutive days backwards from today
        current = 0
        check_date = today
        for d in dates:
            if d == check_date:
                current += 1
                prev = datetime.strptime(check_date, '%Y-%m-%d') - timedelta(days=1)
                check_date = prev.strftime('%Y-%m-%d')
            elif d < check_date:
                break

        # Best streak
        best = 0
        streak = 0
        prev_date = None
        for d in sorted(dates):
            dt_obj = datetime.strptime(d, '%Y-%m-%d')
            if prev_date and (dt_obj - prev_date).days == 1:
                streak += 1
            else:
                streak = 1
            best = max(best, streak)
            prev_date = dt_obj

        return {"current": current, "best": best}

    # ============ Achievements ============

    async def get_user_achievements(self, user_id: int) -> List[str]:
        cur = await self.conn.execute(
            "SELECT achievement_id FROM user_achievements WHERE user_id=?", (user_id,)
        )
        return [row[0] for row in await cur.fetchall()]

    async def unlock_achievement(self, user_id: int, achievement_id: str) -> bool:
        """Returns True if newly unlocked, False if already had it."""
        now_ts = int(datetime.now(MSK).timestamp())
        try:
            await self.conn.execute(
                "INSERT INTO user_achievements (user_id, achievement_id, unlocked_at) VALUES (?,?,?)",
                (user_id, achievement_id, now_ts)
            )
            await self.conn.commit()
            return True
        except Exception:
            return False

    async def check_achievements(self, user_id: int) -> List[str]:
        """Check and unlock any new achievements. Returns list of newly unlocked IDs."""
        existing = set(await self.get_user_achievements(user_id))
        newly_unlocked = []

        # first_food: at least 1 food entry
        if 'first_food' not in existing:
            cur = await self.conn.execute(
                "SELECT COUNT(*) FROM food_entries WHERE user_id=?", (user_id,)
            )
            if (await cur.fetchone())[0] > 0:
                if await self.unlock_achievement(user_id, 'first_food'):
                    newly_unlocked.append('first_food')

        # streak_7, streak_30
        streak = await self.get_food_streak(user_id)
        if 'streak_7' not in existing and streak['current'] >= 7:
            if await self.unlock_achievement(user_id, 'streak_7'):
                newly_unlocked.append('streak_7')
        if 'streak_30' not in existing and streak['current'] >= 30:
            if await self.unlock_achievement(user_id, 'streak_30'):
                newly_unlocked.append('streak_30')

        # sleep_7: 7 consecutive days of sleep logging
        if 'sleep_7' not in existing:
            cur = await self.conn.execute(
                "SELECT DISTINCT entry_date FROM sleep_entries WHERE user_id=? ORDER BY entry_date DESC",
                (user_id,)
            )
            sleep_dates = [row[0] for row in await cur.fetchall()]
            if len(sleep_dates) >= 7:
                today = datetime.now(MSK).strftime('%Y-%m-%d')
                sleep_streak = 0
                check = today
                for d in sleep_dates:
                    if d == check:
                        sleep_streak += 1
                        prev = datetime.strptime(check, '%Y-%m-%d') - timedelta(days=1)
                        check = prev.strftime('%Y-%m-%d')
                    elif d < check:
                        break
                if sleep_streak >= 7:
                    if await self.unlock_achievement(user_id, 'sleep_7'):
                        newly_unlocked.append('sleep_7')

        # workouts_10, workouts_30
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM workout_entries WHERE user_id=?", (user_id,)
        )
        workout_count = (await cur.fetchone())[0]
        if 'workouts_10' not in existing and workout_count >= 10:
            if await self.unlock_achievement(user_id, 'workouts_10'):
                newly_unlocked.append('workouts_10')
        if 'workouts_30' not in existing and workout_count >= 30:
            if await self.unlock_achievement(user_id, 'workouts_30'):
                newly_unlocked.append('workouts_30')

        # mindful_10: 10 meals without gadgets
        if 'mindful_10' not in existing:
            cur = await self.conn.execute(
                "SELECT COUNT(*) FROM food_entries WHERE user_id=? AND ate_without_gadgets=1", (user_id,)
            )
            if (await cur.fetchone())[0] >= 10:
                if await self.unlock_achievement(user_id, 'mindful_10'):
                    newly_unlocked.append('mindful_10')

        # weekly_first: viewed at least one weekly summary
        if 'weekly_first' not in existing:
            cur = await self.conn.execute(
                "SELECT COUNT(*) FROM weekly_summaries WHERE user_id=?", (user_id,)
            )
            if (await cur.fetchone())[0] > 0:
                if await self.unlock_achievement(user_id, 'weekly_first'):
                    newly_unlocked.append('weekly_first')

        return newly_unlocked

    # ============ Admin Analytics ============

    async def count_total_users(self) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) FROM users")
        return (await cur.fetchone())[0]

    async def count_active_users(self) -> int:
        now_ts = int(datetime.now(MSK).timestamp())
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE expires_at > ?", (now_ts,)
        )
        return (await cur.fetchone())[0]

    async def count_new_users(self, days: int) -> int:
        cutoff = int(datetime.now(MSK).timestamp()) - days * 86400
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM payments WHERE created_at > ? AND status='succeeded'",
            (cutoff,)
        )
        return (await cur.fetchone())[0]

    async def sum_revenue(self, days: int) -> int:
        cutoff = int(datetime.now(MSK).timestamp()) - days * 86400
        cur = await self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE created_at > ? AND status='succeeded'",
            (cutoff,)
        )
        return (await cur.fetchone())[0]

    async def total_revenue(self) -> int:
        cur = await self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status='succeeded'"
        )
        return (await cur.fetchone())[0]

    async def get_cancellation_reasons_breakdown(self) -> Dict[str, int]:
        cur = await self.conn.execute(
            "SELECT reason, COUNT(*) FROM cancellations GROUP BY reason"
        )
        return {row[0]: row[1] for row in await cur.fetchall()}

    async def get_daily_new_users(self, days: int) -> List[Dict]:
        """Daily count of first-time paying users."""
        cutoff = int(datetime.now(MSK).timestamp()) - days * 86400
        cur = await self.conn.execute(
            """
            SELECT date(created_at, 'unixepoch', '+3 hours') as d, COUNT(DISTINCT user_id)
            FROM payments WHERE created_at > ? AND status='succeeded'
            GROUP BY d ORDER BY d
            """,
            (cutoff,)
        )
        return [{"date": row[0], "count": row[1]} for row in await cur.fetchall()]

    async def get_daily_revenue(self, days: int) -> List[Dict]:
        cutoff = int(datetime.now(MSK).timestamp()) - days * 86400
        cur = await self.conn.execute(
            """
            SELECT date(created_at, 'unixepoch', '+3 hours') as d, COALESCE(SUM(amount), 0)
            FROM payments WHERE created_at > ? AND status='succeeded'
            GROUP BY d ORDER BY d
            """,
            (cutoff,)
        )
        return [{"date": row[0], "amount": row[1]} for row in await cur.fetchall()]

    async def get_feature_usage_stats(self) -> Dict:
        now_ts = int(datetime.now(MSK).timestamp())
        cur = await self.conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN food_tracker_enabled=1 THEN 1 ELSE 0 END) as food,
                SUM(CASE WHEN sleep_tracker_enabled=1 THEN 1 ELSE 0 END) as sleep,
                SUM(CASE WHEN weekly_review_enabled=1 THEN 1 ELSE 0 END) as weekly
            FROM user_profiles up
            JOIN users u ON up.user_id = u.user_id
            WHERE u.expires_at > ?
            """,
            (now_ts,)
        )
        row = await cur.fetchone()
        total = row[0] or 1
        return {
            "food_tracker_pct": round((row[1] or 0) / total, 2),
            "sleep_tracker_pct": round((row[2] or 0) / total, 2),
            "weekly_review_pct": round((row[3] or 0) / total, 2),
        }

    async def get_avg_food_entries_per_day(self) -> float:
        now_ts = int(datetime.now(MSK).timestamp())
        cur = await self.conn.execute(
            """
            SELECT CAST(COUNT(*) AS FLOAT) / MAX(1, COUNT(DISTINCT entry_date))
            FROM food_entries f
            JOIN users u ON f.user_id = u.user_id
            WHERE u.expires_at > ?
            """,
            (now_ts,)
        )
        row = await cur.fetchone()
        return round(row[0] or 0, 1)

    async def get_auto_renewal_count(self) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE auto_renewal=1 AND payment_method_id IS NOT NULL"
        )
        return (await cur.fetchone())[0]

    async def get_referral_stats_admin(self) -> Dict:
        cur = await self.conn.execute("SELECT COUNT(*) FROM referrals")
        total = (await cur.fetchone())[0]
        cur = await self.conn.execute("SELECT COUNT(*) FROM referrals WHERE referred_paid=1")
        paid = (await cur.fetchone())[0]
        cur = await self.conn.execute("SELECT COUNT(*) FROM referral_rewards WHERE used=0")
        rewards = (await cur.fetchone())[0]
        return {"total_referrals": total, "total_paid": paid, "total_rewards": rewards}

    # ============ Broadcast ============

    async def get_all_user_ids(self) -> List[int]:
        cur = await self.conn.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]

    async def get_expired_user_ids(self) -> List[int]:
        now_ts = int(datetime.now(MSK).timestamp())
        cur = await self.conn.execute(
            "SELECT user_id FROM users WHERE expires_at IS NULL OR expires_at = 0 OR expires_at <= ?",
            (now_ts,)
        )
        return [r[0] for r in await cur.fetchall()]

    async def get_active_user_ids(self) -> List[int]:
        now_ts = int(datetime.now(MSK).timestamp())
        cur = await self.conn.execute(
            "SELECT user_id FROM users WHERE expires_at > ?", (now_ts,)
        )
        return [r[0] for r in await cur.fetchall()]

    async def log_broadcast(self, admin_id: int, segment: str, message_text: str,
                             sent: int, failed: int, blocked: int):
        now_ts = int(datetime.now(MSK).timestamp())
        await self.conn.execute(
            """INSERT INTO broadcast_log (admin_id, segment, message_text, sent_count, failed_count, blocked_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (admin_id, segment, message_text, sent, failed, blocked, now_ts)
        )
        await self.conn.commit()


# Singleton instance
db = HabitDB()
