# app.py
# Telegram-бот подписки (aiogram v3, YooKassa, SQLite)
# — Запрашивает телефон, формирует чек (54-ФЗ)
# — Медиа из .env (WELCOME_VIDEO, FORMAL_PHOTO)
# — НЕТ служебных отчётов пользователю
# — CSV-логи: starts.csv, payments.csv, cancellations.csv

import asyncio
import csv
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Optional, Iterable

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand
)
from dotenv import load_dotenv
from yookassa import Configuration, Payment
from yookassa.domain.exceptions import ApiError

# ---------- ЛОГИ ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("bot")

# ---------- CONFIG ----------
load_dotenv()

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v if v != "" else None

def _env_int(name: str, default: int) -> int:
    try:
        v = _env(name)
        return int(v) if v is not None else default
    except Exception:
        return default

def _fallback_media() -> tuple[str, str]:
    # поддерживаем и нормальные ключи, и «варианты с опечатками»
    welcome_video = _env("WELCOME_VIDEO") or _env("VIDEOID") or ""
    formal_photo  = _env("FORMAL_PHOTO")  or _env("PHOTO_ID") or _env("PHOTO ID") or ""
    return welcome_video, formal_photo


BOT_TOKEN = _env("BOT_TOKEN")
GROUP_ID = _env_int("GROUP_ID", 0)

# админские ID для служебных команд (через запятую в .env)
_ADMIN_IDS_RAW = _env("ADMIN_IDS") or ""
ADMIN_IDS = {int(x) for x in re.split(r"[,\s]+", _ADMIN_IDS_RAW) if x.isdigit()}

def _is_admin_id(uid: int) -> bool:
    # если список пуст — не ограничиваем (любая команда пройдёт)
    return (not ADMIN_IDS) or (uid in ADMIN_IDS)

MONTH_PRICE = _env_int("MONTH_PRICE", 0)
BASE_PRICE_TEXT = _env("BASE_PRICE_TEXT")
PROMO_PRICE_TEXT = _env("PROMO_PRICE_TEXT")

SHOP_ID = _env("SHOP_ID")
SHOP_SECRET_KEY = _env("SHOP_SECRET_KEY")

VAT_CODE = _env_int("VAT_CODE", 1)  # 1=без НДС; 2=0%; 3=10%; 4=20%; 5=10/110; 6=20/120
TAX_SYSTEM_CODE = _env("TAX_SYSTEM_CODE")  # например "1" (ОСН)
RECEIPT_ITEM_DESCRIPTION = _env("RECEIPT_ITEM_DESCRIPTION") or "Подписка на марафон (30 дней)"

WELCOME_VIDEO, FORMAL_PHOTO = _fallback_media()

DB_PATH = _env("DB_PATH") or "bot.db"
INVITE_TTL_HOURS = _env_int("INVITE_TTL_HOURS", 24)
PAID_DAYS = _env_int("PAID_DAYS", 30)
GRACE_DAYS = _env_int("GRACE_DAYS", 1)
CHECK_INTERVAL_SEC = _env_int("CHECK_INTERVAL_SEC", 1800)

# YooKassa
Configuration.account_id = SHOP_ID
Configuration.secret_key = SHOP_SECRET_KEY

# CSV файлы
STARTS_CSV = _env("STARTS_CSV") or "starts.csv"
PAYMENTS_CSV = _env("PAYMENTS_CSV") or "payments.csv"
CANCELS_CSV = _env("CANCELS_CSV") or "cancellations.csv"

def _csv_append(path: str, row: list[str]):
    try:
        exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(["ts_iso", "user_id", "username", "full_name", "extra"])
            w.writerow(row)
    except Exception as e:
        log.error("CSV append failed (%s): %s", path, e)

def log_cancellation(user_id: int, reason: str):
    """Логирует отмену подписки в CSV файл"""
    _csv_append(CANCELS_CSV, [
        now_iso(), str(user_id), "", "", reason
    ])

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
bot_username_cache: Optional[str] = None

CANCEL_REASONS: list[tuple[str, str]] = [
    ("Дорого", "price"),
    ("Нет времени", "time"),
    ("Тех. проблемы", "tech"),
    ("Нашёл другой формат", "other_service"),
    ("Другая причина", "other"),
]

# ---------- УТИЛИТЫ ----------
MSK = timezone(timedelta(hours=3))

def now_ts() -> int:
    return int(datetime.now(MSK).timestamp())

def now_iso() -> str:
    return datetime.now(MSK).strftime("%Y-%m-%d %H:%M:%S%z")

def days_left(expires_at: int, at_ts: Optional[int] = None) -> int:
    ref = at_ts or now_ts()
    return max(0, (expires_at - ref) // 86400)

def add_days_ts(days: int) -> int:
    return int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())

def add_hours_ts(hours: int) -> int:
    return int((datetime.now(timezone.utc) + timedelta(hours=hours)).timestamp())

def is_active(expires_at: Optional[int]) -> bool:
    return bool(expires_at and expires_at > now_ts())

def normalize_phone(raw: str) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return None
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if not digits.startswith("+"):
        digits = "+" + digits
    if len(re.sub(r"\D+", "", digits)) < 11:
        return None
    return digits

def kb(rows: Iterable[Iterable[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])

def kb_row(*buttons: InlineKeyboardButton) -> list[InlineKeyboardButton]:
    return list(buttons)

def ask_phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажми, чтобы отправить номер"
    )

def price_text_block() -> str:
    base = BASE_PRICE_TEXT or (f"{MONTH_PRICE}₽" if MONTH_PRICE > 0 else "")
    parts = []
    if base:
        parts.append(f"💳 Ежемесячная подписка — {base}.")
    if PROMO_PRICE_TEXT:
        parts.append(f"🎁 {PROMO_PRICE_TEXT}")
    return "\n".join(parts) if parts else ""

async def replace_with_text(cb: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    try:
        await cb.message.delete()
    except Exception:
        try:
            await cb.message.edit_caption(caption=text, reply_markup=reply_markup)
            return
        except Exception:
            pass
    await cb.message.answer(text, reply_markup=reply_markup)

async def send_video_or_text(chat_id: int, video_id_or_url: str, caption: str, reply_markup=None):
    try:
        if video_id_or_url:
            await bot.send_video(chat_id=chat_id, video=video_id_or_url, caption=caption, reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id, caption, reply_markup=reply_markup)
    except Exception as e:
        logging.error("send_video failed: %s", e)
        await bot.send_message(chat_id, caption, reply_markup=reply_markup)

async def send_photo_or_text(chat_id: int, photo_id_or_url: str, caption: str, reply_markup=None):
    try:
        if photo_id_or_url:
            await bot.send_photo(chat_id=chat_id, photo=photo_id_or_url, caption=caption, reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id, caption, reply_markup=reply_markup)
    except Exception as e:
        logging.error("send_photo failed: %s", e)
        await bot.send_message(chat_id, caption, reply_markup=reply_markup)

# ---------- БАЗА ----------
DDL_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    full_name  TEXT,
    expires_at INTEGER DEFAULT 0,
    phone      TEXT,
    remind_3_sent INTEGER DEFAULT 0,
    remind_2_sent INTEGER DEFAULT 0,
    remind_1_sent INTEGER DEFAULT 0
);
"""
DDL_PAYMENTS = """
CREATE TABLE IF NOT EXISTS payments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    payment_id TEXT,
    amount     INTEGER,
    status     TEXT,
    created_at INTEGER
);
"""
DDL_CANCEL = """
CREATE TABLE IF NOT EXISTS cancellations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    reason     TEXT,
    created_at INTEGER
);
"""
DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_expires ON users(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_payments_pid ON payments(payment_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_uid ON payments(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_cancellations_uid ON cancellations(user_id)"
]

@dataclass
class UserRow:
    user_id: int
    expires_at: int

class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("PRAGMA synchronous=NORMAL;")
        await self.conn.execute("PRAGMA foreign_keys=ON;")
        await self.conn.commit()

    async def init_schema(self):
        assert self.conn is not None
        await self.conn.execute(DDL_USERS)
        await self.conn.execute(DDL_PAYMENTS)
        await self.conn.execute(DDL_CANCEL)
        for stmt in DDL_INDEXES:
            await self.conn.execute(stmt)
        # на случай старой БД — тихая миграция phone
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN phone TEXT;")
        except Exception:
            pass
        # Миграции для напоминаний
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN remind_3_sent INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN remind_2_sent INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN remind_1_sent INTEGER DEFAULT 0;")
        except Exception:
            pass
        # Автопродление + рефералка
        for col, defn in [
            ("payment_method_id", "TEXT"),
            ("auto_renewal", "INTEGER DEFAULT 0"),
            ("auto_renewal_agreed_at", "INTEGER"),
            ("auto_renewal_failures", "INTEGER DEFAULT 0"),
            ("referral_code", "TEXT"),
        ]:
            try:
                await self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn};")
            except Exception:
                pass
        # Рефералы, награды, достижения, broadcast
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL, referred_id INTEGER NOT NULL,
                referred_paid INTEGER DEFAULT 0, reward_granted INTEGER DEFAULT 0,
                created_at INTEGER, UNIQUE(referred_id)
            )""")
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS referral_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, discount_percent INTEGER DEFAULT 30,
                used INTEGER DEFAULT 0, created_at INTEGER
            )""")
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, achievement_id TEXT NOT NULL,
                unlocked_at INTEGER, UNIQUE(user_id, achievement_id)
            )""")
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL, segment TEXT NOT NULL,
                message_text TEXT NOT NULL, sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0, blocked_count INTEGER DEFAULT 0,
                created_at INTEGER
            )""")
        await self.conn.commit()

    async def upsert_user_meta(self, user, expires_at: Optional[int] = None):
        assert self.conn is not None
        if expires_at is None:
            await self.conn.execute(
                "INSERT OR IGNORE INTO users(user_id, username, full_name) VALUES(?,?,?)",
                (user.id, user.username, user.full_name)
            )
        else:
            await self.conn.execute(
                """
                INSERT INTO users(user_id, username, full_name, expires_at)
                VALUES(?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    expires_at=excluded.expires_at
                """,
                (user.id, user.username, user.full_name, expires_at)
            )
        await self.conn.commit()

    async def get_user(self, uid: int) -> Optional[UserRow]:
        assert self.conn is not None
        cur = await self.conn.execute("SELECT user_id, expires_at FROM users WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        return UserRow(row[0], row[1]) if row else None

    async def set_user_expires(self, uid: int, expires_at: int,
                               username: Optional[str] = None, full_name: Optional[str] = None):
        assert self.conn is not None
        await self.conn.execute(
            """
            INSERT INTO users(user_id, username, full_name, expires_at, remind_3_sent, remind_2_sent, remind_1_sent)
            VALUES(?,?,?,?,0,0,0)
            ON CONFLICT(user_id) DO UPDATE SET
              expires_at=excluded.expires_at,
              username=COALESCE(excluded.username, users.username),
              full_name=COALESCE(excluded.full_name, users.full_name),
              remind_3_sent=0,
              remind_2_sent=0,
              remind_1_sent=0
            """,
            (uid, username, full_name, expires_at)
        )
        await self.conn.commit()

    async def set_user_phone(self, uid: int, phone: str):
        assert self.conn is not None
        await self.conn.execute(
            """
            INSERT INTO users(user_id, phone) VALUES(?,?)
            ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone
            """,
            (uid, phone)
        )
        await self.conn.commit()

    async def get_user_phone(self, uid: int) -> Optional[str]:
        assert self.conn is not None
        cur = await self.conn.execute("SELECT phone FROM users WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else None

    async def mark_reminder_sent(self, uid: int, days: int):
        assert self.conn is not None
        col = {3: "remind_3_sent", 2: "remind_2_sent", 1: "remind_1_sent"}.get(days)
        if not col:
            return
        await self.conn.execute(f"UPDATE users SET {col}=1 WHERE user_id=?", (uid,))
        await self.conn.commit()

    async def save_payment(self, user_id: int, payment_id: str, amount: int, status: str):
        assert self.conn is not None
        await self.conn.execute(
            "INSERT INTO payments(user_id, payment_id, amount, status, created_at) VALUES(?,?,?,?,?)",
            (user_id, payment_id, amount, status, now_ts())
        )
        await self.conn.commit()

    async def update_payment_status(self, payment_id: str, status: str):
        assert self.conn is not None
        await self.conn.execute("UPDATE payments SET status=? WHERE payment_id=?", (status, payment_id))
        await self.conn.commit()

    async def save_cancellation(self, user_id: int, reason: str):
        assert self.conn is not None
        await self.conn.execute(
            "INSERT INTO cancellations(user_id, reason, created_at) VALUES(?,?,?)",
            (user_id, reason, now_ts())
        )
        await self.conn.commit()

    async def get_user_id_by_username(self, username: str) -> Optional[int]:
        assert self.conn is not None
        username = username.lstrip("@").lower()
        cur = await self.conn.execute("SELECT user_id FROM users WHERE LOWER(IFNULL(username,'')) = ? LIMIT 1", (username,))
        row = await cur.fetchone()
        return row[0] if row else None

    async def expired_user_ids(self, at_ts: int) -> list[int]:
        assert self.conn is not None
        cur = await self.conn.execute("SELECT user_id FROM users WHERE expires_at > 0 AND expires_at < ?", (at_ts,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

    # --- Автопродление ---
    async def set_payment_method(self, uid: int, payment_method_id: str):
        assert self.conn is not None
        await self.conn.execute(
            "UPDATE users SET payment_method_id=?, auto_renewal=1, auto_renewal_agreed_at=? WHERE user_id=?",
            (payment_method_id, now_ts(), uid))
        await self.conn.commit()

    async def set_auto_renewal(self, uid: int, enabled: bool):
        assert self.conn is not None
        await self.conn.execute(
            "UPDATE users SET auto_renewal=? WHERE user_id=?", (1 if enabled else 0, uid))
        await self.conn.commit()

    async def get_auto_renewal_info(self, uid: int) -> dict:
        assert self.conn is not None
        cur = await self.conn.execute(
            "SELECT auto_renewal, payment_method_id, auto_renewal_failures FROM users WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        if not row:
            return {"enabled": False, "has_payment_method": False, "failures": 0}
        return {
            "enabled": bool(row[0]),
            "has_payment_method": bool(row[1]),
            "failures": row[2] or 0,
        }

    async def clear_payment_method(self, uid: int):
        assert self.conn is not None
        await self.conn.execute(
            "UPDATE users SET payment_method_id=NULL, auto_renewal=0, auto_renewal_failures=0 WHERE user_id=?",
            (uid,))
        await self.conn.commit()

    async def get_users_for_auto_renewal(self, within_seconds: int = 172800) -> list[dict]:
        """Пользователи с auto_renewal=1, истекающие в ближайшие within_seconds (по умолчанию 2 дня)."""
        assert self.conn is not None
        now = now_ts()
        deadline = now + within_seconds
        cur = await self.conn.execute(
            """SELECT user_id, username, full_name, expires_at, payment_method_id, auto_renewal_failures
               FROM users
               WHERE auto_renewal=1 AND payment_method_id IS NOT NULL
                 AND expires_at > ? AND expires_at <= ?
                 AND auto_renewal_failures < 2""",
            (now, deadline))
        rows = await cur.fetchall()
        return [{"user_id": r[0], "username": r[1], "full_name": r[2],
                 "expires_at": r[3], "payment_method_id": r[4], "failures": r[5] or 0}
                for r in rows]

    async def increment_auto_renewal_failures(self, uid: int):
        assert self.conn is not None
        await self.conn.execute(
            "UPDATE users SET auto_renewal_failures = COALESCE(auto_renewal_failures,0)+1 WHERE user_id=?", (uid,))
        await self.conn.commit()

    async def reset_auto_renewal_failures(self, uid: int):
        assert self.conn is not None
        await self.conn.execute("UPDATE users SET auto_renewal_failures=0 WHERE user_id=?", (uid,))
        await self.conn.commit()

    # --- Рефералка ---
    async def get_referral_code(self, uid: int) -> Optional[str]:
        assert self.conn is not None
        cur = await self.conn.execute("SELECT referral_code FROM users WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else None

    async def set_referral_code(self, uid: int, code: str):
        assert self.conn is not None
        await self.conn.execute("UPDATE users SET referral_code=? WHERE user_id=?", (code, uid))
        await self.conn.commit()

    async def find_user_by_referral_code(self, code: str) -> Optional[int]:
        assert self.conn is not None
        cur = await self.conn.execute("SELECT user_id FROM users WHERE referral_code=?", (code,))
        row = await cur.fetchone()
        return row[0] if row else None

    async def create_referral(self, referrer_id: int, referred_id: int):
        assert self.conn is not None
        try:
            await self.conn.execute(
                "INSERT INTO referrals(referrer_id, referred_id, created_at) VALUES(?,?,?)",
                (referrer_id, referred_id, now_ts()))
            await self.conn.commit()
        except Exception:
            pass  # duplicate

    async def get_referral_for_user(self, referred_id: int) -> Optional[dict]:
        assert self.conn is not None
        cur = await self.conn.execute(
            "SELECT referrer_id, referred_paid, reward_granted FROM referrals WHERE referred_id=?", (referred_id,))
        row = await cur.fetchone()
        if not row:
            return None
        return {"referrer_id": row[0], "referred_paid": bool(row[1]), "reward_granted": bool(row[2])}

    async def mark_referral_paid(self, referred_id: int):
        assert self.conn is not None
        await self.conn.execute(
            "UPDATE referrals SET referred_paid=1, reward_granted=1 WHERE referred_id=? AND referred_paid=0",
            (referred_id,))
        await self.conn.commit()

    async def get_unused_referral_reward(self, uid: int) -> Optional[int]:
        """Возвращает discount_percent если есть неиспользованная награда."""
        assert self.conn is not None
        cur = await self.conn.execute(
            "SELECT id, discount_percent FROM referral_rewards WHERE user_id=? AND used=0 ORDER BY created_at LIMIT 1",
            (uid,))
        row = await cur.fetchone()
        return row[1] if row else None

    async def use_referral_reward(self, uid: int):
        assert self.conn is not None
        await self.conn.execute(
            """UPDATE referral_rewards SET used=1 WHERE id=(
                 SELECT id FROM referral_rewards WHERE user_id=? AND used=0 ORDER BY created_at LIMIT 1
               )""", (uid,))
        await self.conn.commit()

    async def create_referral_reward(self, uid: int, discount_percent: int = 30):
        assert self.conn is not None
        await self.conn.execute(
            "INSERT INTO referral_rewards(user_id, discount_percent, created_at) VALUES(?,?,?)",
            (uid, discount_percent, now_ts()))
        await self.conn.commit()

    async def get_referral_stats(self, uid: int) -> dict:
        assert self.conn is not None
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,))
        total = (await cur.fetchone())[0]
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND referred_paid=1", (uid,))
        paid = (await cur.fetchone())[0]
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM referral_rewards WHERE user_id=? AND used=0", (uid,))
        rewards = (await cur.fetchone())[0]
        return {"total_invited": total, "total_paid": paid, "available_rewards": rewards}

    # --- Broadcast / Сегменты ---
    async def get_all_user_ids(self) -> list[int]:
        assert self.conn is not None
        cur = await self.conn.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]

    async def get_active_user_ids(self) -> list[int]:
        assert self.conn is not None
        cur = await self.conn.execute(
            "SELECT user_id FROM users WHERE expires_at > ?", (now_ts(),))
        return [r[0] for r in await cur.fetchall()]

    async def get_expired_user_ids_all(self) -> list[int]:
        assert self.conn is not None
        cur = await self.conn.execute(
            "SELECT user_id FROM users WHERE expires_at > 0 AND expires_at < ?", (now_ts(),))
        return [r[0] for r in await cur.fetchall()]

    async def log_broadcast(self, admin_id: int, segment: str, text: str,
                            sent: int, failed: int, blocked: int):
        assert self.conn is not None
        await self.conn.execute(
            """INSERT INTO broadcast_log(admin_id, segment, message_text, sent_count,
               failed_count, blocked_count, created_at) VALUES(?,?,?,?,?,?,?)""",
            (admin_id, segment, text, sent, failed, blocked, now_ts()))
        await self.conn.commit()

db = DB(DB_PATH)

# ---------- ТЕКСТЫ / КНОПКИ ----------
def _welcome_text() -> str:
    head = (
        "🏋️‍♀️ Ты в пространстве функционального тренинга Насти Петуховой\n\n"
        "📌 Подписка даёт доступ к:\n"
        "— Тренировкам «повторяй за мной» (дома, минимум оборудования)\n"
        "— Рекомендациям по питанию\n"
        "— Экспресс-комплексам, растяжке, разминке/заминке\n"
        "— Закрытому комьюнити\n\n"
    )
    pb = price_text_block()
    return head + pb if pb else head

WELCOME_TEXT = _welcome_text()

FORM_TEXT = (
    "Для начала пара формальностей 💌\n\n"
    "Нужно принять условия и указать номер телефона, он нужен для выставления чека."
)

def terms_kb() -> InlineKeyboardMarkup:
    return kb([
        kb_row(InlineKeyboardButton(
            text="Политика конфиденциальности",
            url="https://docs.google.com/document/d/1-0iG8VOz8T3jKnJRgFI_zGBFf8rvYBWtY8AEfqFgu1A/edit?usp=sharing"
        )),
        kb_row(InlineKeyboardButton(
            text="Оферта",
            url="https://docs.google.com/document/d/1huoHqUnMRl3SFE8w6VJ546hst3g80wYzF1jyEIasjkQ/edit?usp=sharing"
        )),
        kb_row(InlineKeyboardButton(text="✅ Я согласен(на)", callback_data="agree_terms"))
    ])

def cancel_or_keep_kb() -> InlineKeyboardMarkup:
    return kb([
        kb_row(InlineKeyboardButton(text="Я хочу отменить подписку", callback_data="cancel_reason")),
        kb_row(InlineKeyboardButton(text="Я передумал, хочу остаться", callback_data="cancel_keep"))
    ])

def cancel_reasons_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=title, callback_data=f"cancel_reason:{key}")]
            for (title, key) in CANCEL_REASONS]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="cancel_warn")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def cancel_confirm_kb(reason_key: str) -> InlineKeyboardMarkup:
    return kb([
        kb_row(InlineKeyboardButton(text="Всё равно отменить", callback_data=f"cancel_final:{reason_key}")),
        kb_row(InlineKeyboardButton(text="Я передумал, хочу остаться", callback_data="cancel_keep")),
        kb_row(InlineKeyboardButton(text="Назад", callback_data="cancel_reason"))
    ])

def pay_button_kb(pay_url: str, payment_id: str) -> InlineKeyboardMarkup:
    return kb([
        kb_row(InlineKeyboardButton(text="Оплатить картой (ЮKassa)", url=pay_url)),
        kb_row(InlineKeyboardButton(text="Я оплатил — проверить", callback_data=f"pay_check:{payment_id}"))
    ])

# ---------- ХЭНДЛЕРЫ ----------
@dp.message(CommandStart())
async def start(m: Message):
    await db.upsert_user_meta(m.from_user)

    # Обработка реферальной ссылки (deep link: /start ref_XXXXXX)
    args = m.text.split() if m.text else []
    if len(args) > 1 and args[1].startswith("ref_"):
        referral_code = args[1][4:]  # убрать "ref_"
        if referral_code:
            referrer_id = await db.find_user_by_referral_code(referral_code)
            if referrer_id and referrer_id != m.from_user.id:
                await db.create_referral(referrer_id, m.from_user.id)
                log.info("Referral created: %s -> %s (code %s)", referrer_id, m.from_user.id, referral_code)

    # CSV лог старта
    _csv_append(STARTS_CSV, [
        now_iso(), str(m.from_user.id), f"@{m.from_user.username}" if m.from_user.username else "",
        m.from_user.full_name or "", "start"
    ])

    btn = kb([kb_row(InlineKeyboardButton(text="Что дальше? 💖", callback_data="show_formalities"))])
    await send_video_or_text(m.chat.id, WELCOME_VIDEO or "", WELCOME_TEXT, reply_markup=btn)

@dp.callback_query(F.data == "show_formalities")
async def show_formalities(cb: CallbackQuery):
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await send_photo_or_text(cb.message.chat.id, FORMAL_PHOTO or "", FORM_TEXT, reply_markup=terms_kb())

@dp.callback_query(F.data == "agree_terms")
async def agree_terms(cb: CallbackQuery):
    await cb.answer("Принято ✅")
    row = await db.get_user(cb.from_user.id)
    active = is_active(row.expires_at) if row else False
    phone = await db.get_user_phone(cb.from_user.id)

    if not phone and not active:
        await replace_with_text(
            cb,
            "Чтобы оформить доступ, нужен номер для чека. Нажми кнопку ниже — Telegram передаст его автоматически."
        )
        await bot.send_message(cb.from_user.id, "Поделитесь номером телефона:", reply_markup=ask_phone_kb())
        return

    if active:
        link = await create_one_time_invite()
        if link:
            buttons = kb([kb_row(InlineKeyboardButton(text="Отменить подписку", callback_data="cancel_warn"))])
            await replace_with_text(
                cb,
                "Подписка активна.\n"
                f"<b>Вход в группу:</b> {link}\nСсылка действует 24 часа и на один вход.",
                buttons
            )
        else:
            await replace_with_text(
                cb,
                "Подписка активна, но не удалось создать ссылку приглашения. Проверь права бота и GROUP_ID."
            )
    else:
        text = "Теперь перейдём к оплате: доступ на 1 месяц, оплата на странице ЮKassa."
        buttons = kb([kb_row(InlineKeyboardButton(text="Оформить доступ (1 месяц)", callback_data="pay_start"))])
        await replace_with_text(cb, text, buttons)

@dp.message(Command("status"))
async def status(m: Message):
    row = await db.get_user(m.from_user.id)
    if row and is_active(row.expires_at):
        left = days_left(row.expires_at)
        await m.answer(
            f"Подписка активна. Осталось ≈ {left} дн.",
            reply_markup=kb([kb_row(InlineKeyboardButton(text="Отменить подписку", callback_data="cancel_warn"))])
        )
    else:
        await m.answer("Подписка не активна. Нажми /start и оформи доступ.")

@dp.message(Command("phone"))
async def set_phone_cmd(m: Message):
    parts = m.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await m.answer("Формат: <code>/phone +79991234567</code>")
        return
    phone = normalize_phone(parts[1])
    if not phone:
        await m.answer("Не понял номер. Пример: <code>/phone +79991234567</code>")
        return
    await db.set_user_phone(m.from_user.id, phone)
    await m.answer(f"Телефон сохранён: {phone}")

@dp.message(F.contact)
async def got_contact(m: Message):
    phone = normalize_phone(m.contact.phone_number if m.contact else "")
    if not phone:
        await m.answer("Не удалось распознать номер. Введите его вручную: /phone +79991234567")
        return
    await db.set_user_phone(m.from_user.id, phone)
    await m.answer("Телефон получен. Можно оформлять доступ.", reply_markup=ReplyKeyboardRemove())
    await m.answer(
        "Оформить доступ:",
        reply_markup=kb([kb_row(InlineKeyboardButton(text="Оформить доступ (1 месяц)", callback_data="pay_start"))])
    )

@dp.message(Command("cancel_subscription"))
async def cancel_subscription_cmd(m: Message):
    row = await db.get_user(m.from_user.id)
    if not (row and is_active(row.expires_at)):
        await m.answer("Подписка не активна.")
        return
    await m.answer(
        "⚠️ Если продолжишь, отмена произойдёт моментально. Доступ к группе закроется прямо сейчас.",
        reply_markup=cancel_or_keep_kb()
    )

@dp.callback_query(F.data == "cancel_warn")
async def cancel_warn(cb: CallbackQuery):
    await cb.answer()
    row = await db.get_user(cb.from_user.id)
    if not (row and is_active(row.expires_at)):
        await cb.answer("Подписка не активна.", show_alert=True)
        return
    text = "⚠️ Если продолжишь, отмена произойдёт моментально. Доступ к группе закроется прямо сейчас."
    await replace_with_text(cb, text, cancel_or_keep_kb())

@dp.callback_query(F.data == "cancel_reason")
async def cancel_reason(cb: CallbackQuery):
    await cb.answer()
    await replace_with_text(cb, "Жаль, что решили уйти. Подскажите, почему?", cancel_reasons_kb())

@dp.callback_query(F.data.startswith("cancel_reason:"))
async def cancel_reason_selected(cb: CallbackQuery):
    reason_key = cb.data.split(":", 1)[1]
    title = next((t for t, k in CANCEL_REASONS if k == reason_key), "other")
    text = f"Понимаем: <b>{title}</b>. Остаётесь?"
    await replace_with_text(cb, text, cancel_confirm_kb(reason_key))
    await cb.answer()

@dp.callback_query(F.data == "cancel_keep")
async def cancel_keep(cb: CallbackQuery):
    await cb.answer("Остаёмся 💪")
    await replace_with_text(cb, "Класс, что остались с нами! Если нужна помощь — напишите @petukhovaas.")

async def kick_from_group(uid: int) -> bool:
    """
    Удаляет пользователя из группы (бан на минуту + анбан).
    Возвращает True — если успешно, False — если ошибка.
    """
    try:
        # Проверяем, что бот в группе с нужными правами
        chat_member = await bot.get_chat_member(GROUP_ID, bot.id)
        if not chat_member.can_restrict_members:
            log.error("Bot has no rights to restrict members in group %s", GROUP_ID)
            return False

        # Кик через бан и анбан
        await bot.ban_chat_member(
            GROUP_ID,
            uid,
            until_date=now_ts() + 60  # бан на 60 секунд
        )
        await bot.unban_chat_member(GROUP_ID, uid)
        log.info("User %s successfully kicked from group %s", uid, GROUP_ID)
        return True

    except Exception as e:
        log.error("kick_from_group failed for uid=%s: %s", uid, e)
        return False

# ---- Удаление пользователя из группы (мягкий кик) ----
async def ensure_user_removed(uid: int) -> bool:
    """
    True  — пользователя точно нет в группе (уже вышел/кикнут) или кик прошёл успешно.
    False — пользователь остаётся в группе (нет прав/ошибка).
    """
    try:
        member = await bot.get_chat_member(GROUP_ID, uid)
        status = getattr(member, "status", None)

        # Уже не состоит
        if status in ("left", "kicked"):
            return True

        # Можно кикнуть (ban+unban = «мягкий кик»)
        if status not in ("administrator", "creator"):
            try:
                await bot.ban_chat_member(GROUP_ID, uid, until_date=now_ts() + 60)
                await bot.unban_chat_member(GROUP_ID, uid)
                return True
            except Exception as e:
                log.error("ban/unban failed for uid=%s: %s", uid, e)
                return False

        # Админов кикать нельзя
        return False

    except Exception as e:
        # Обычно USER_NOT_PARTICIPANT — считаем, что он уже не в чате
        log.info("get_chat_member failed for uid=%s: %s (treat as removed)", uid, e)
        return True



@dp.callback_query(F.data.startswith("cancel_final:"))
async def cancel_final(cb: CallbackQuery):
    reason_key = cb.data.split(":", 1)[1]

    # 1) Закрываем доступ в базе (сразу, без условий)
    await db.set_user_expires(
        cb.from_user.id,
        now_ts() - 1,                    # гарантированно в прошлом
        cb.from_user.username,
        cb.from_user.full_name
    )
    await db.save_cancellation(cb.from_user.id, reason_key)
    # Отключаем автопродление и удаляем сохранённый способ оплаты
    await db.clear_payment_method(cb.from_user.id)
    log_cancellation(cb.from_user.id, reason_key)

    # 2) Пытаемся удалить из группы
    kicked = await ensure_user_removed(cb.from_user.id)

    # 3) Сообщаем результат
    if kicked:
        await replace_with_text(cb, "Подписка отменена. Доступ закрыт.")
    else:
        await replace_with_text(
            cb,
            "Подписка отменена. Доступ закрыт.\n"
            "Удалить из группы сейчас не удалось. Проверьте у бота право "
            "«Блокировка пользователей» и что он админ именно этого чата. "
            "Если участник остался — удалите вручную."
        )

    try:
        await cb.answer("Отменено")
    except Exception:
        pass

# ---- Инвайт в группу ----
async def create_one_time_invite() -> Optional[str]:
    if not str(GROUP_ID).startswith("-100"):
        log.error("GROUP_ID выглядит странно: %s (должен начинаться с -100...)", GROUP_ID)
    try:
        link = await bot.create_chat_invite_link(
            chat_id=GROUP_ID,
            name=f"access-{now_ts()}",
            expire_date=add_hours_ts(INVITE_TTL_HOURS),
            member_limit=1
        )
        return link.invite_link
    except Exception as e:
        log.error("create_one_time_invite failed: %s", e)
        return None

# ---- YooKassa: старт платежа ----
@dp.callback_query(F.data == "pay_start")
async def pay_start(cb: CallbackQuery):
    await cb.answer("Открываю платёж…")
    global bot_username_cache

    user = cb.from_user

    # сумма для ЮKassa
    amount_rub = f"{MONTH_PRICE}.00"

    # берём телефон из базы (он обязателен)
    phone = await db.get_user_phone(user.id)
    if not phone:
        # если телефона нет — стопаем покупку, просим дать номер
        await replace_with_text(
            cb,
            "Перед оплатой нужен номер телефона для чека. Нажми «Поделиться номером»."
        )
        await bot.send_message(
            user.id,
            "Поделитесь номером телефона:",
            reply_markup=ask_phone_kb()
        )
        return

    # формируем описание платежа для ЮKassa
    # добавляем и user.id, и телефон
    description = (
        f"{RECEIPT_ITEM_DESCRIPTION}, "
        f"user_id={user.id}, "
        f"phone={phone}"
    )

    # формируем return_url (куда ЮKassa вернёт после оплаты)
    if not bot_username_cache:
        me = await bot.me()
        bot_username_cache = me.username
    return_url = f"https://t.me/{bot_username_cache}"

    # формируем чек (receipt), который уйдёт в фискализацию
    receipt = {
        "customer": {
            "phone": phone   # <- ЮKassa использует это, чтобы отправить чек клиенту
        },
        "items": [{
            "description": RECEIPT_ITEM_DESCRIPTION,
            "quantity": "1.00",
            "amount": {
                "value": amount_rub,
                "currency": "RUB"
            },
            "vat_code": VAT_CODE
        }]
    }

    # система налогообложения если задана
    if TAX_SYSTEM_CODE:
        try:
            receipt["tax_system_code"] = int(TAX_SYSTEM_CODE)
        except Exception:
            log.warning("Некорректный TAX_SYSTEM_CODE в .env: %r", TAX_SYSTEM_CODE)

    # Проверяем реферальную скидку
    referral_discount = await db.get_unused_referral_reward(user.id)
    if referral_discount:
        discount_amount = MONTH_PRICE * referral_discount // 100
        final_price = MONTH_PRICE - discount_amount
        amount_rub = f"{final_price}.00"
        await db.use_referral_reward(user.id)
        log.info("User %s using referral discount %d%% — price %d -> %d", user.id, referral_discount, MONTH_PRICE, final_price)

    # создаём платёж в ЮKassa
    try:
        payment = await asyncio.wait_for(
            asyncio.to_thread(partial(Payment.create, {
                "amount": {
                    "value": amount_rub,
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,
                "save_payment_method": True,
                "description": description,          # <- телефон теперь попадает в description
                "metadata": {
                    "user_id": str(user.id),
                    "phone": phone                    # <- дублируем телефон в metadata, чтобы потом можно было сверить
                },
                "receipt": receipt                    # <- чек с телефоном
            })),
            timeout=15
        )
    except ApiError as e:
        # например, магазин не принимает фискальные данные / неверный ИНН и т.д.
        try:
            log.error("YooKassa ApiError %s %s", getattr(e, "code", "?"), e.message)
        except Exception:
            pass
        await replace_with_text(
            cb,
            "Платёж временно недоступен. Попробуйте позже."
        )
        return
    except asyncio.TimeoutError:
        await replace_with_text(
            cb,
            "Платёжный сервис отвечает дольше обычного. Попробуйте позже."
        )
        return
    except Exception as e:
        log.exception("YooKassa unknown error: %s", e)
        await replace_with_text(
            cb,
            "Платёж сейчас недоступен. Проверьте настройки и попробуйте позже."
        )
        return

    # даём пользователю кнопку «оплатить» и потом «проверить»
    pay_url = payment.confirmation.confirmation_url
    discount_note = ""
    if referral_discount:
        discount_note = f"\n🎁 Применена реферальная скидка {referral_discount}%! Сумма: {amount_rub} ₽\n"
    await replace_with_text(
        cb,
        (
            "Откроется платёжная страница ЮKassa.\n"
            "После оплаты вернись сюда и нажми «Проверить».\n\n"
            f"Чек уйдёт на номер: {phone}\n"
            f"{discount_note}"
            "\n<i>Нажимая «Оплатить», вы соглашаетесь на сохранение способа оплаты "
            "для автоматического продления подписки. Отключить: /autorenewal</i>"
        ),
        pay_button_kb(pay_url, payment.id)
    )

    # пишем платёж в БД (статус пока, скорее всего, 'pending')
    await db.save_payment(user.id, payment.id, MONTH_PRICE, payment.status)

# ---- Проверка платежа ----
@dp.callback_query(F.data.startswith("pay_check:"))
async def pay_check(cb: CallbackQuery):
    payment_id = cb.data.split(":", 1)[1]
    await cb.answer("Проверяю платёж…")

    try:
        payment = await asyncio.wait_for(
            asyncio.to_thread(Payment.find_one, payment_id),
            timeout=10
        )
    except asyncio.TimeoutError:
        await replace_with_text(
            cb,
            "ЮKassa отвечает дольше обычного. Нажмите «Проверить ещё раз» чуть позже.",
            kb([kb_row(InlineKeyboardButton(text="Проверить ещё раз", callback_data=f"pay_check:{payment_id}"))])
        )
        return
    except Exception as e:
        log.exception("YooKassa find_one error: %s", e)
        await replace_with_text(
            cb,
            "Не удалось проверить. Попробуйте ещё раз.",
            kb([kb_row(InlineKeyboardButton(text="Проверить ещё раз", callback_data=f"pay_check:{payment_id}"))])
        )
        return

    status = payment.status
    await db.update_payment_status(payment_id, status)

    # --- добавлено: получаем телефон пользователя
    phone = await db.get_user_phone(cb.from_user.id)
    phone_text = f"Чек придёт на номер: {phone}" if phone else ""

    if status == "succeeded":
        desired_expires = add_days_ts(PAID_DAYS + GRACE_DAYS)
        existing = await db.get_user(cb.from_user.id)
        new_expires = max(desired_expires, existing.expires_at if existing else 0)
        await db.upsert_user_meta(cb.from_user, expires_at=new_expires)

        # Сохраняем способ оплаты для автопродления
        try:
            pm = payment.payment_method
            if pm and getattr(pm, "saved", False) and pm.id:
                await db.set_payment_method(cb.from_user.id, pm.id)
                log.info("Payment method %s saved for user %s", pm.id, cb.from_user.id)
        except Exception as e:
            log.warning("Could not save payment method for user %s: %s", cb.from_user.id, e)

        # Обработка реферала — если этого пользователя пригласили
        try:
            ref = await db.get_referral_for_user(cb.from_user.id)
            if ref and not ref["referred_paid"]:
                await db.mark_referral_paid(cb.from_user.id)
                await db.create_referral_reward(ref["referrer_id"], 30)
                # Уведомляем реферера
                try:
                    await bot.send_message(
                        ref["referrer_id"],
                        "🎉 Твой друг оплатил подписку!\n"
                        "Тебе начислена скидка 30% на следующий месяц.\n"
                        "Она применится автоматически при следующей оплате."
                    )
                except Exception:
                    pass
        except Exception as e:
            log.warning("Referral reward error for user %s: %s", cb.from_user.id, e)

        # CSV лог оплаты
        _csv_append(PAYMENTS_CSV, [
            now_iso(), str(cb.from_user.id),
            f"@{cb.from_user.username}" if cb.from_user.username else "",
            cb.from_user.full_name or "",
            f"amount={MONTH_PRICE}; payment_id={payment_id}; phone={phone or '-'}"
        ])

        link = await create_one_time_invite()
        if link:
            await replace_with_text(
                cb,
                "Оплата прошла, спасибо! ✅\n"
                f"<b>Вход в группу:</b> {link}\n"
                f"Ссылка одноразовая, действует {INVITE_TTL_HOURS} часов.\n\n"
                f"{phone_text}"
            )
            # второе сообщение — «уютный чат»
            await bot.send_message(
                cb.from_user.id,
                "И добро пожаловать в наш уютный чат 🐥\n"
                "Здесь мы общаемся, делимся впечатлениями от тренировок, результатами, "
                "поддерживаем и вдохновляем друг друга. Это наше место силы 💛\n\n"
                "Даже если подписка закончится — вход сюда всегда открыт.\n\n"
                "https://t.me/+JNeWx7UUJXcxZjAy"
            )
        else:
            await replace_with_text(
                cb,
                "Оплата прошла ✅, но ссылку в группу создать не удалось. Проверь права бота и GROUP_ID.\n\n"
                f"{phone_text}"
            )
    else:
        # Для pending показываем и кнопку оплаты, и кнопку проверки
        pay_url = payment.confirmation.confirmation_url
        await replace_with_text(
            cb,
            f"Статус платежа: <b>{status}</b>.\nЕсли уже оплатили — подождите пару секунд и нажмите «Проверить ещё раз».\n\n{phone_text}",
            pay_button_kb(pay_url, payment_id)
        )


# ---- Периодические проверки срока подписки ----
async def periodic_checks():
    """
    Каждые CHECK_INTERVAL_SEC:
    1) Берём всех просроченных из БД.
    2) Для каждого уточняем реальный статус в чате:
       - left/kicked/ошибка получения статуса → считаем, что его уже нет,
         обнуляем expires_at (чтобы больше не трогать).
       - administrator/creator → пропускаем.
       - member/restricted → мягко кикаем (ban+unban). Если успешно — обнуляем expires_at.
    """
    while True:
        try:
            now = now_ts()
            ids = await db.expired_user_ids(now)
            for uid in ids:
                # 2.1 пытаемся узнать реальный статус в группе
                try:
                    member = await bot.get_chat_member(GROUP_ID, uid)
                    status = getattr(member, "status", None)
                except Exception as e:
                    # например USER_NOT_PARTICIPANT — считаем, что уже вне чата
                    log.info("get_chat_member failed for uid=%s: %s (treat as removed)", uid, e)
                    status = "left"

                if status in ("left", "kicked", None):
                    # Уже вне чата — помечаем как обработанного, чтобы не перебирать постоянно
                    await db.set_user_expires(uid, 0)
                    continue

                if status in ("administrator", "creator"):
                    # Админов не трогаем
                    log.debug("skip admin/creator uid=%s", uid)
                    continue

                # Обычный участник — пробуем мягкий кик
                removed = await ensure_user_removed(uid)
                if removed:
                    await db.set_user_expires(uid, 0)
                else:
                    log.warning("could not remove uid=%s (still member)", uid)

        except Exception as e:
            log.error("periodic_checks error: %s", e)

        await asyncio.sleep(CHECK_INTERVAL_SEC)


# ---- Автоочистка истёкших пользователей ----
async def auto_clean_expired():
    """
    Каждые 60 минут проверяет базу (users) и кикает всех, у кого подписка истекла (expires_at <= now() или NULL).
    Логирует количество найденных пользователей, успешные и неуспешные кики.
    Использует ban_chat_member + unban_chat_member для мягкого кика.
    """
    while True:
        try:
            log.info("auto_clean_expired: запущена проверка истёкших пользователей")
            now = now_ts()
            # Получаем всех пользователей, у кого подписка истекла или не указана (NULL/0/expired)
            async with db.conn.execute(
                "SELECT user_id FROM users WHERE expires_at IS NULL OR expires_at = 0 OR expires_at <= ?", (now,)
            ) as cur:
                rows = await cur.fetchall()
                expired_ids = [row[0] for row in rows]
            total = len(expired_ids)
            log.info("auto_clean_expired: найдено %d истёкших пользователей", total)
            kicked = 0
            not_kicked = 0
            for uid in expired_ids:
                try:
                    # Мягкий кик: ban + unban
                    await bot.ban_chat_member(GROUP_ID, uid, until_date=now + 60)
                    await bot.unban_chat_member(GROUP_ID, uid)
                    kicked += 1
                    log.info("auto_clean_expired: успешно кикнут uid=%s", uid)
                except Exception as e:
                    not_kicked += 1
                    log.warning("auto_clean_expired: не удалось кикнуть uid=%s: %s", uid, e)
            log.info(
                "auto_clean_expired: завершено. Всего: %d, кикнуто: %d, не удалось кикнуть: %d",
                total, kicked, not_kicked
            )
        except Exception as e:
            log.error("auto_clean_expired error: %s", e)
        await asyncio.sleep(60 * 60)  # 60 минут


# ---- Уведомления об окончании подписки за 3/2/1 день ----
async def reminder_notifier():
    """
    Каждые 30 минут:
    - находит пользователей, у кого до конца подписки осталось ≤ N дней (N ∈ {3,2,1})
    - у кого соответствующее напоминание ещё не отправлялось (remind_N_sent = 0)
    - шлёт личное сообщение и отмечает отправку, чтобы не спамить
    """
    CHECK_EVERY = 30 * 60
    while True:
        try:
            now = now_ts()
            for days, col in [(3, "remind_3_sent"), (2, "remind_2_sent"), (1, "remind_1_sent")]:
                # условие: expires_at > now (подписка ещё активна) и осталось не больше N дней
                # чтобы не проскочить из-за даунтайма — если бот был оффлайн, всё равно отправим при первой возможности
                sql = f"""
                    SELECT user_id, expires_at
                    FROM users
                    WHERE expires_at > ?
                      AND (? + {days}*86400) >= expires_at
                      AND COALESCE({col},0)=0
                """
                async with db.conn.execute(sql, (now, now)) as cur:
                    rows = await cur.fetchall()
                for uid, exp in rows:
                    left = max(0, (exp - now) // 86400)
                    # Проверяем автопродление
                    ar_info = await db.get_auto_renewal_info(uid)
                    try:
                        if ar_info["enabled"] and ar_info["has_payment_method"]:
                            txt = (
                                f"Напоминание: до конца подписки осталось {left} дн.\n"
                                "Подписка продлится автоматически 🔄\n"
                                "Управление: /autorenewal"
                            )
                        elif days > 1:
                            txt = f"Напоминание: до конца подписки осталось {left} дн."
                        else:
                            txt = (
                                "Напоминание: остался последний день подписки. Завтра доступ закроется. "
                                "Продлите, чтобы сохранить доступ 😊"
                            )
                        await bot.send_message(uid, txt)
                        await db.mark_reminder_sent(uid, days)
                        log.info("reminder %sd sent to %s", days, uid)
                    except Exception as e:
                        log.warning("reminder: failed to DM uid=%s: %s", uid, e)
        except Exception as e:
            log.error("reminder_notifier error: %s", e)
        await asyncio.sleep(CHECK_EVERY)


# ---- Автопродление подписки ----
AUTO_RENEWAL_INTERVAL = 6 * 3600  # каждые 6 часов

async def auto_renewal_job():
    """
    Каждые 6 часов:
    - Находит пользователей с auto_renewal=1, у кого подписка истекает в ближайшие 2 дня
    - Создаёт рекуррентный платёж по сохранённому payment_method_id
    - При успехе — продляет подписку и уведомляет
    - При неудаче — инкрементирует failures, после 2 — отключает auto_renewal
    """
    while True:
        try:
            users = await db.get_users_for_auto_renewal()
            if users:
                log.info("auto_renewal_job: %d users to process", len(users))

            for u in users:
                uid = u["user_id"]
                pm_id = u["payment_method_id"]
                try:
                    amount_rub = f"{MONTH_PRICE}.00"
                    phone = await db.get_user_phone(uid)

                    receipt_data = {}
                    if phone:
                        receipt_data = {
                            "receipt": {
                                "customer": {"phone": phone},
                                "items": [{
                                    "description": RECEIPT_ITEM_DESCRIPTION,
                                    "quantity": "1.00",
                                    "amount": {"value": amount_rub, "currency": "RUB"},
                                    "vat_code": VAT_CODE
                                }]
                            }
                        }
                        if TAX_SYSTEM_CODE:
                            try:
                                receipt_data["receipt"]["tax_system_code"] = int(TAX_SYSTEM_CODE)
                            except Exception:
                                pass

                    payment = await asyncio.wait_for(
                        asyncio.to_thread(partial(Payment.create, {
                            "amount": {"value": amount_rub, "currency": "RUB"},
                            "payment_method_id": pm_id,
                            "capture": True,
                            "description": f"Автопродление подписки, user_id={uid}",
                            "metadata": {"user_id": str(uid), "type": "auto_renewal"},
                            **receipt_data
                        })),
                        timeout=15
                    )

                    if payment.status == "succeeded":
                        new_expires = add_days_ts(PAID_DAYS + GRACE_DAYS)
                        existing = await db.get_user(uid)
                        final_expires = max(new_expires, existing.expires_at if existing else 0)
                        await db.set_user_expires(uid, final_expires, u.get("username"), u.get("full_name"))
                        await db.reset_auto_renewal_failures(uid)
                        await db.save_payment(uid, payment.id, MONTH_PRICE, "succeeded")
                        log.info("auto_renewal succeeded for user %s, payment %s", uid, payment.id)

                        try:
                            await bot.send_message(
                                uid,
                                "✅ Подписка автоматически продлена!\n"
                                f"Списано: {MONTH_PRICE} ₽\n"
                                "Отключить автопродление: /autorenewal"
                            )
                        except Exception:
                            pass
                    else:
                        raise Exception(f"Payment status: {payment.status}")

                except Exception as e:
                    log.warning("auto_renewal failed for user %s: %s", uid, e)
                    await db.increment_auto_renewal_failures(uid)

                    info = await db.get_auto_renewal_info(uid)
                    if info["failures"] >= 2:
                        await db.set_auto_renewal(uid, False)
                        try:
                            await bot.send_message(
                                uid,
                                "⚠️ Не удалось продлить подписку автоматически (2 попытки).\n"
                                "Автопродление отключено. Продлите вручную: /start"
                            )
                        except Exception:
                            pass
                    else:
                        try:
                            await bot.send_message(
                                uid,
                                "⚠️ Не удалось списать оплату для продления подписки.\n"
                                "Повторим попытку позже. Если проблема сохранится — продлите вручную: /start"
                            )
                        except Exception:
                            pass

                await asyncio.sleep(2)  # rate limit

        except Exception as e:
            log.error("auto_renewal_job error: %s", e)

        await asyncio.sleep(AUTO_RENEWAL_INTERVAL)


# ---- Команда синхронизации для админов ----
@dp.message(Command("admin_sync"))
async def admin_sync(m: Message):
    if not _is_admin_id(m.from_user.id):
        await m.answer("Команда доступна только админам.")
        return

    processed_left = 0
    processed_kicked = 0
    skipped_admin = 0

    ids = await db.expired_user_ids(now_ts())
    for uid in ids:
        try:
            member = await bot.get_chat_member(GROUP_ID, uid)
            status = getattr(member, "status", None)
        except Exception:
            status = "left"

        if status in ("left", "kicked", None):
            await db.set_user_expires(uid, 0)
            processed_left += 1
            continue

        if status in ("administrator", "creator"):
            skipped_admin += 1
            continue

        if await ensure_user_removed(uid):
            await db.set_user_expires(uid, 0)
            processed_kicked += 1

    await m.answer(
        "Синхронизация завершена:\n"
        f"— уже вне чата (помечены): {processed_left}\n"
        f"— кикнуто: {processed_kicked}\n"
        f"— админов пропущено: {skipped_admin}"
    )


# ---- /myid: показать свой Telegram ID ----
@dp.message(Command("myid"))
async def myid_cmd(m: Message):
    await m.answer(f"Ваш ID: <code>{m.from_user.id}</code>")

# ---- /comp: админ выдаёт/продлевает подписку и получает подтверждение ----
async def _do_comp(m: Message):
    if not _is_admin_id(m.from_user.id):
        await m.answer("Команда доступна только админам.")
        return

    parts = m.text.strip().split()
    if len(parts) != 3:
        await m.answer("Формат: <code>/comp &lt;user_id|@username&gt; &lt;days&gt;</code>")
        return

    target_raw = parts[1]
    try:
        days = int(parts[2])
        if days <= 0:
            raise ValueError
    except Exception:
        await m.answer("Количество дней должно быть положительным целым числом.")
        return

    uid: Optional[int] = None
    if target_raw.startswith("@"):
        uid = await db.get_user_id_by_username(target_raw)
        if uid is None:
            await m.answer(f"Не нашёл пользователя по нику {target_raw}. Сначала он должен написать боту /start.")
            return
    else:
        try:
            uid = int(target_raw)
        except Exception:
            await m.answer("user_id должен быть числом или используйте @username.")
            return

    row = await db.get_user(uid)
    now = now_ts()
    old_expires = row.expires_at if row else 0
    base_ts = old_expires if old_expires and old_expires > now else now
    new_expires = base_ts + days * 86400

    await db.set_user_expires(uid, new_expires)

    # Создаём одноразовую ссылку в группу, чтобы сразу выдать доступ вместе с уведомлением
    link = await create_one_time_invite()
    link_block = (
        f"\n\n<b>Вход в группу:</b> {link}\nСсылка одноразовая, действует {INVITE_TTL_HOURS} часов."
        if link else
        "\n\nНе удалось создать ссылку приглашения (проверьте права бота в группе)."
    )

    # Уведомляем пользователя
    try:
        await bot.send_message(
            uid,
            (
                "Ваша подписка продлена администратором на "
                f"{days} дн. Новая дата истечения: "
                f"{datetime.fromtimestamp(new_expires, MSK).strftime('%d.%m.%Y %H:%M')} MSK"
                + link_block
            )
        )
    except Exception as e:
        log.warning("notify comp to %s failed: %s", uid, e)

    # Ответ админу с итогами и (если получилось) ссылкой
    was_days = max(0, (old_expires - now) // 86400) if old_expires else 0
    now_days = max(0, (new_expires - now) // 86400)
    dt_human = datetime.fromtimestamp(new_expires, MSK).strftime("%d.%m.%Y %H:%M")

    await m.answer(
        "✅ Подписка обновлена\n"
        f"Пользователь: <code>{uid}</code>\n"
        f"Выдано: <b>{days}</b> дн.\n"
        f"Было: <b>{was_days}</b> дн.\n"
        f"Стало: <b>{now_days}</b> дн.\n"
        f"Истекает: <b>{dt_human} MSK</b>"
        + (f"\n\n<b>Вход в группу:</b> {link}\nСсылка одноразовая, действует {INVITE_TTL_HOURS} часов." if link else "")
    )

@dp.message(Command("comp"))
async def comp_cmd(m: Message):
    # Основная ветка — когда Telegram корректно пометил сообщение как bot_command
    await _do_comp(m)

# Fallback: если по какой-то причине entity bot_command отсутствует,
# ловим обычный текст, начинающийся с /comp (или /comp@YourBodyPet_bot)
@dp.message(F.text.as_("t"))
async def comp_cmd_fallback(m: Message, t: Optional[str]):
    if not t:
        return
    txt = t.strip()
    if re.match(r"^/comp(\b|@)", txt, flags=re.IGNORECASE):
        await _do_comp(m)

# ---- /revoke: админ отменяет подписку пользователя ----
@dp.message(Command("revoke"))
async def revoke_subscription_cmd(m: Message):
    if not _is_admin_id(m.from_user.id):
        await m.answer("Команда доступна только админам.")
        return

    parts = m.text.strip().split()
    if len(parts) != 2:
        await m.answer("Формат: <code>/revoke &lt;user_id|@username&gt;</code>")
        return

    target_raw = parts[1]
    uid: Optional[int] = None

    if target_raw.startswith("@"):
        uid = await db.get_user_id_by_username(target_raw)
        if uid is None:
            await m.answer(f"Не нашёл пользователя по нику {target_raw}.")
            return
    else:
        try:
            uid = int(target_raw)
        except Exception:
            await m.answer("user_id должен быть числом или используйте @username.")
            return

    # Проверяем есть ли пользователь в БД
    row = await db.get_user(uid)
    if not row:
        await m.answer(f"Пользователь {uid} не найден в базе данных.")
        return

    # Проверяем активна ли подписка
    if not is_active(row.expires_at):
        await m.answer(f"У пользователя {uid} ({row.username or row.full_name}) уже нет активной подписки.")
        return

    # Отменяем подписку (устанавливаем expires_at в прошлое)
    await db.set_user_expires(
        uid,
        now_ts() - 1,  # в прошлом
        row.username,
        row.full_name
    )
    await db.save_cancellation(uid, "admin_revoke")
    log_cancellation(uid, "admin_revoke")

    # Пытаемся кикнуть из группы
    kicked = await ensure_user_removed(uid)
    kick_status = "кикнут из группы" if kicked else "не удалось кикнуть (возможно уже вышел)"

    # Уведомляем админа
    user_info = row.username if row.username else row.full_name or f"ID {uid}"
    await m.answer(
        f"✅ Подписка отменена для пользователя {user_info}\n"
        f"— Статус: {kick_status}\n"
        f"— Дата отмены: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    # Уведомляем пользователя
    try:
        await bot.send_message(
            uid,
            "⚠️ Ваша подписка была отменена администратором.\n"
            "Если у вас есть вопросы, напишите @petukhovaas"
        )
    except Exception as e:
        log.warning(f"Не удалось отправить уведомление пользователю {uid}: {e}")

# ---- Команда /autorenewal ----
@dp.message(Command("autorenewal"))
async def autorenewal_cmd(m: Message):
    info = await db.get_auto_renewal_info(m.from_user.id)

    if info["enabled"] and info["has_payment_method"]:
        text = (
            "🔄 <b>Автопродление включено</b>\n\n"
            "Подписка будет продлеваться автоматически.\n"
            "Стоимость списывается с сохранённого способа оплаты."
        )
        buttons = kb([
            kb_row(InlineKeyboardButton(text="❌ Отключить автопродление", callback_data="autorenew_off")),
            kb_row(InlineKeyboardButton(text="✅ Оставить как есть", callback_data="autorenew_keep"))
        ])
    elif info["has_payment_method"]:
        text = (
            "🔄 <b>Автопродление отключено</b>\n\n"
            "Способ оплаты сохранён. Вы можете включить автопродление."
        )
        buttons = kb([
            kb_row(InlineKeyboardButton(text="🔄 Включить автопродление", callback_data="autorenew_on")),
            kb_row(InlineKeyboardButton(text="Оставить выключенным", callback_data="autorenew_keep"))
        ])
    else:
        text = (
            "🔄 <b>Автопродление недоступно</b>\n\n"
            "Способ оплаты будет сохранён при следующей оплате подписки, "
            "и автопродление включится автоматически."
        )
        buttons = None

    await m.answer(text, reply_markup=buttons)

@dp.callback_query(F.data == "autorenew_on")
async def autorenew_on(cb: CallbackQuery):
    await db.set_auto_renewal(cb.from_user.id, True)
    await cb.answer("Автопродление включено ✅")
    await replace_with_text(cb, "🔄 Автопродление <b>включено</b>.\nПодписка будет продлеваться автоматически.")

@dp.callback_query(F.data == "autorenew_off")
async def autorenew_off(cb: CallbackQuery):
    await db.set_auto_renewal(cb.from_user.id, False)
    await cb.answer("Автопродление отключено")
    await replace_with_text(cb, "🔄 Автопродление <b>отключено</b>.\nПодписка будет действовать до конца оплаченного периода.")

@dp.callback_query(F.data == "autorenew_keep")
async def autorenew_keep(cb: CallbackQuery):
    await cb.answer("Хорошо!")
    info = await db.get_auto_renewal_info(cb.from_user.id)
    status = "включено" if info["enabled"] else "отключено"
    await replace_with_text(cb, f"🔄 Автопродление <b>{status}</b>. Настройки не изменены.")


# ---- Команда /referral ----
import string as _string
import secrets as _secrets

def _generate_referral_code(length: int = 6) -> str:
    chars = _string.ascii_uppercase + _string.digits
    return ''.join(_secrets.choice(chars) for _ in range(length))

@dp.message(Command("referral"))
async def referral_cmd(m: Message):
    row = await db.get_user(m.from_user.id)
    if not (row and is_active(row.expires_at)):
        await m.answer("Реферальная программа доступна только для подписчиков. Оформите подписку: /start")
        return

    # Генерируем код если нет
    code = await db.get_referral_code(m.from_user.id)
    if not code:
        for _ in range(10):
            code = _generate_referral_code()
            existing = await db.find_user_by_referral_code(code)
            if not existing:
                break
        await db.set_referral_code(m.from_user.id, code)

    stats = await db.get_referral_stats(m.from_user.id)
    bot_me = await bot.me()
    ref_link = f"https://t.me/{bot_me.username}?start=ref_{code}"

    text = (
        "🎁 <b>Реферальная программа</b>\n\n"
        f"Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        "Поделись ею с друзьями! Когда друг оплатит подписку, "
        "ты получишь <b>скидку 30%</b> на следующий месяц.\n\n"
        f"📊 Приглашено: {stats['total_invited']}\n"
        f"💰 Оплатили: {stats['total_paid']}\n"
        f"🎁 Доступные скидки: {stats['available_rewards']}"
    )

    buttons = kb([
        kb_row(InlineKeyboardButton(
            text="📤 Поделиться ссылкой",
            switch_inline_query=f"Присоединяйся к тренировкам! 🏋️‍♀️ {ref_link}"
        ))
    ])

    await m.answer(text, reply_markup=buttons)


# ---- Habit Tracker Integration ----
# Импортируем обработчики habit tracker
try:
    from habit_handlers import register_habit_handlers, init_habit_db, start_notification_scheduler
    HABIT_TRACKER_ENABLED = True
    log.info("Habit tracker module loaded")
except ImportError as e:
    HABIT_TRACKER_ENABLED = False
    log.warning("Habit tracker module not available: %s", e)

# ---- Startup ----
async def on_startup():
    await db.connect()
    await db.init_schema()
    asyncio.create_task(periodic_checks())
    asyncio.create_task(auto_clean_expired())
    asyncio.create_task(reminder_notifier())
    asyncio.create_task(auto_renewal_job())

    # Инициализируем habit tracker если доступен
    if HABIT_TRACKER_ENABLED:
        try:
            await init_habit_db()
            start_notification_scheduler(bot)
            log.info("Habit tracker initialized")
        except Exception as e:
            log.error("Failed to initialize habit tracker: %s", e)

    # Обновляем список команд бота
    commands = [
        BotCommand(command="start", description="Начать"),
        BotCommand(command="status", description="Статус подписки"),
        BotCommand(command="cancel_subscription", description="Отменить подписку"),
        BotCommand(command="comp", description="(admin) Выдать подписку"),
        BotCommand(command="revoke", description="(admin) Отменить подписку пользователя"),
        BotCommand(command="myid", description="Показать мой ID"),
        BotCommand(command="autorenewal", description="Управление автопродлением"),
        BotCommand(command="referral", description="Реферальная программа"),
    ]

    # Добавляем команды habit tracker если доступен
    if HABIT_TRACKER_ENABLED:
        commands.append(BotCommand(command="habits", description="Ассистент привычек"))
        commands.append(BotCommand(command="food", description="Как добавить еду"))

    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        log.warning("set_my_commands failed: %s", e)

def main():
    # Регистрируем обработчики habit tracker
    if HABIT_TRACKER_ENABLED:
        register_habit_handlers(dp)

    dp.startup.register(on_startup)
    dp.run_polling(bot)

if __name__ == "__main__":
    main()
