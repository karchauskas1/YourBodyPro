# habit_handlers.py
# Обработчики для habit tracker, интегрируемые в основной бот (app.py)
#
# Для интеграции добавьте в app.py:
# 1. В начало файла: from habit_handlers import register_habit_handlers, init_habit_db
# 2. В on_startup(): await init_habit_db()
# 3. После создания dp: register_habit_handlers(dp)

import asyncio
import base64
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# Импортируем из webapp/backend
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp/backend'))

from database import HabitDB
from llm_service import analyze_food_photo, analyze_food_text, generate_daily_summary

log = logging.getLogger("habit_handlers")
MSK = timezone(timedelta(hours=3))

# URL веб-приложения (настраивается в .env)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://app.pasekaproduction.ru")
WEBAPP_CACHE_BUSTER = os.getenv("WEBAPP_CACHE_BUSTER", "20260630-app-domain")


def webapp_url(path: str = "") -> str:
    base_url = WEBAPP_URL.rstrip("/")
    if not base_url:
        return ""
    clean_path = path if path.startswith("/") or not path else f"/{path}"
    url = f"{base_url}{clean_path}"
    if not WEBAPP_CACHE_BUSTER:
        return url

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["v"] = WEBAPP_CACHE_BUSTER
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

# Database instance
habit_db: Optional[HabitDB] = None


async def init_habit_db():
    """Инициализация базы данных для habit tracker"""
    global habit_db
    habit_db = HabitDB(os.path.join(os.path.dirname(__file__), 'bot.db'))
    await habit_db.connect()
    await habit_db.init_schema()
    log.info("Habit tracker database initialized")


def register_habit_handlers(dp: Dispatcher):
    """Регистрация обработчиков для habit tracker"""

    # ============ Команды ============

    @dp.message(Command("habits"))
    async def habits_command(m: Message):
        """Открыть веб-приложение ассистента привычек"""
        # Проверяем подписку (используем существующую функцию из app.py)
        from app import db as main_db, is_active

        user = await main_db.get_user(m.from_user.id)
        if not user or not is_active(user.expires_at):
            await m.answer(
                "Ассистент привычек доступен только с активной подпиской.\n"
                "Нажми /start чтобы оформить доступ."
            )
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✨ Открыть ассистент привычек",
                web_app={"url": webapp_url()}
            )]
        ])

        await m.answer(
            "🌱 Ассистент привычек\n\n"
            "Помогает освоить полезные привычки без давления и подсчётов:\n"
            "• Food tracker с AI-анализом\n"
            "• Трекер сна\n"
            "• Вечерние итоги и недельные обзоры\n\n"
            "Нажми кнопку ниже:",
            reply_markup=keyboard
        )

    @dp.message(Command("food"))
    async def food_command(m: Message):
        """Информация о добавлении еды"""
        await m.answer(
            "🍽️ <b>Как добавить еду:</b>\n\n"
            "1. Отправь <b>фото</b> еды — AI распознает продукты\n"
            "2. Или напиши <b>текстом</b>, например:\n"
            "   <i>салат с курицей и хлеб</i>\n\n"
            "Данные копятся в течение дня, вечером получишь итог."
        )

    # ============ Обработка фото еды ============

    @dp.message(F.photo)
    async def handle_photo(m: Message):
        """Обработать фото как еду (если food tracker включён)"""
        global habit_db
        if not habit_db:
            return

        # Проверяем, включён ли food tracker у пользователя
        profile = await habit_db.get_user_profile(m.from_user.id)
        if not profile or not profile.get('food_tracker_enabled'):
            # Если food tracker не включён, игнорируем фото
            return

        # Проверяем подписку
        if not await habit_db.is_subscription_active(m.from_user.id):
            return

        await m.answer("📸 Анализирую фото...")

        try:
            # Получаем фото максимального размера
            photo = m.photo[-1]
            file = await m.bot.get_file(photo.file_id)
            file_path = file.file_path

            # Скачиваем файл
            from aiogram import Bot
            bot: Bot = m.bot
            file_bytes = await bot.download_file(file_path)
            photo_base64 = base64.b64encode(file_bytes.read()).decode('utf-8')

            # Анализируем через LLM
            analysis = await analyze_food_photo(photo_base64, m.caption)

            # Сохраняем в БД
            await habit_db.add_food_entry(
                user_id=m.from_user.id,
                description=analysis.get('description', 'Фото еды'),
                photo_file_id=photo.file_id,
                categories=analysis.get('categories'),
                raw_input=m.caption,
                source='telegram'
            )

            # Отправляем подтверждение
            products = analysis.get('products', [])
            if products:
                products_text = ", ".join(products[:5])
                if len(products) > 5:
                    products_text += f" и ещё {len(products) - 5}"
                await m.answer(f"✅ Записал: {products_text}")
            else:
                await m.answer(f"✅ Записал: {analysis.get('description', 'еда')}")

        except Exception as e:
            log.error(f"Failed to process food photo: {e}")
            await m.answer("Не удалось обработать фото. Попробуй ещё раз.")

    # ============ Обработка текста как еды ============

    # Паттерны для определения, что текст похож на описание еды
    FOOD_PATTERNS = [
        r'^съел', r'^ел[аи]?', r'^поел', r'^обед', r'^завтрак', r'^ужин',
        r'^перекус', r'^еда:', r'на завтрак', r'на обед', r'на ужин',
        r'^каша', r'^салат', r'^суп', r'^курица', r'^рыба', r'^мясо',
        r'^овощи', r'^фрукты', r'^творог', r'^йогурт', r'^яйц',
    ]

    @dp.message(F.text)
    async def handle_text(m: Message):
        """Обработать текст как еду если похоже на описание"""
        global habit_db
        if not habit_db:
            return

        # Игнорируем команды
        if m.text.startswith('/'):
            return

        # Проверяем, включён ли food tracker
        profile = await habit_db.get_user_profile(m.from_user.id)
        if not profile or not profile.get('food_tracker_enabled'):
            return

        # Проверяем подписку
        if not await habit_db.is_subscription_active(m.from_user.id):
            return

        # Проверяем, похож ли текст на описание еды
        text_lower = m.text.lower().strip()
        is_food = any(re.search(pattern, text_lower) for pattern in FOOD_PATTERNS)

        # Также считаем едой если текст короткий и содержит слова-продукты
        food_words = ['салат', 'суп', 'каша', 'курица', 'рыба', 'мясо', 'овощи',
                      'творог', 'йогурт', 'яйца', 'хлеб', 'рис', 'гречка', 'макароны',
                      'сыр', 'молоко', 'кефир', 'фрукты', 'яблоко', 'банан']

        if not is_food and len(text_lower.split()) <= 10:
            is_food = any(word in text_lower for word in food_words)

        if not is_food:
            return

        try:
            # Анализируем текст
            analysis = await analyze_food_text(m.text)

            # Сохраняем в БД
            await habit_db.add_food_entry(
                user_id=m.from_user.id,
                description=analysis.get('description', m.text),
                categories=analysis.get('categories'),
                raw_input=m.text,
                source='telegram'
            )

            # Отправляем подтверждение
            await m.answer(f"✅ Записал: {analysis.get('description', m.text)}")

        except Exception as e:
            log.error(f"Failed to process food text: {e}")

    # ============ Обработка ответов о сне ============

    @dp.callback_query(F.data.startswith("sleep:"))
    async def handle_sleep_callback(cb: CallbackQuery):
        """Обработать ответ на вопрос о сне"""
        global habit_db
        if not habit_db:
            await cb.answer("Ошибка")
            return

        try:
            score = int(cb.data.split(":")[1])
            if not 1 <= score <= 5:
                await cb.answer("Неверная оценка")
                return

            # Сохраняем в БД
            success = await habit_db.add_sleep_entry(cb.from_user.id, score)

            if success:
                labels = {
                    1: "Очень плохо 😴",
                    2: "Плохо 😕",
                    3: "Нормально 😐",
                    4: "Хорошо 🙂",
                    5: "Отлично 😊"
                }

                # Редактируем сообщение
                await cb.message.edit_text(
                    f"☀️ Доброе утро!\n\nКак ты сегодня спал(а)?\n\n"
                    f"<b>Ответ:</b> {labels.get(score, str(score))}\n\n"
                    "Хорошего дня! ✨"
                )
                await cb.answer("Записал!")
            else:
                await cb.answer("Не удалось сохранить")

        except Exception as e:
            log.error(f"Failed to handle sleep callback: {e}")
            await cb.answer("Ошибка")


# ============ Планировщик уведомлений ============

async def notification_scheduler(bot):
    """
    Планировщик уведомлений.
    Запускается как asyncio task и проверяет каждую минуту.
    """
    global habit_db
    if not habit_db:
        log.error("habit_db not initialized for scheduler")
        return

    log.info("Notification scheduler started")
    while True:
        try:
            # Получаем текущее UTC время
            now_utc = datetime.now(timezone.utc)

            # ---- Утренние вопросы о сне ----
            morning_users = await habit_db.get_users_for_notification('morning')
            for user_data in morning_users:
                user_id = user_data['user_id']
                notification_time = user_data['notification_time']  # '10:00'
                timezone_offset = user_data['timezone_offset']  # 180 для MSK, 240 для Dubai, и т.д.

                # Вычисляем локальное время пользователя
                user_tz = timezone(timedelta(minutes=timezone_offset))
                user_local_time = now_utc.astimezone(user_tz)
                user_current_time = user_local_time.strftime('%H:%M')
                user_today = user_local_time.strftime('%Y-%m-%d')

                # Проверяем, совпадает ли текущее локальное время с настройкой
                if user_current_time == notification_time:
                    existing = await habit_db.get_sleep_entry(user_id, user_today)
                    if existing is None:
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [
                                InlineKeyboardButton(text="😴 1", callback_data="sleep:1"),
                                InlineKeyboardButton(text="😕 2", callback_data="sleep:2"),
                                InlineKeyboardButton(text="😐 3", callback_data="sleep:3"),
                                InlineKeyboardButton(text="🙂 4", callback_data="sleep:4"),
                                InlineKeyboardButton(text="😊 5", callback_data="sleep:5"),
                            ]
                        ])
                        try:
                            await bot.send_message(
                                user_id,
                                "☀️ Доброе утро!\n\nКак ты сегодня спал(а)?",
                                reply_markup=keyboard
                            )
                            log.info(f"Sent morning sleep question to {user_id} (local time: {user_current_time})")
                        except Exception as e:
                            log.warning(f"Failed to send sleep question to {user_id}: {e}")

            # ---- Вечерние итоги ----
            evening_users = await habit_db.get_users_for_notification('evening')
            for user_data in evening_users:
                user_id = user_data['user_id']
                notification_time = user_data['notification_time']  # '21:00'
                timezone_offset = user_data['timezone_offset']

                # Вычисляем локальное время пользователя
                user_tz = timezone(timedelta(minutes=timezone_offset))
                user_local_time = now_utc.astimezone(user_tz)
                user_current_time = user_local_time.strftime('%H:%M')
                user_today = user_local_time.strftime('%Y-%m-%d')

                # Проверяем, совпадает ли текущее локальное время с настройкой
                if user_current_time == notification_time:
                    food_entries = await habit_db.get_food_entries_for_date(user_id, user_today)

                    if food_entries:
                        # Генерируем итог если нужно
                        existing_summary = await habit_db.get_daily_summary(user_id, user_today)
                        if not existing_summary:
                            profile = await habit_db.get_user_profile(user_id)
                            user_goal = profile.get('goal', 'maintain') if profile else 'maintain'
                            summary = await generate_daily_summary(food_entries, user_goal)
                            await habit_db.save_daily_summary(user_id, user_today, summary)

                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(
                                text="📊 Посмотреть итог",
                                web_app={"url": webapp_url("/summary")}
                            )]
                        ])
                        try:
                            await bot.send_message(
                                user_id,
                                "🌙 Твой вечерний итог готов!\n\n"
                                "Посмотри, как прошёл день с точки зрения питания.",
                                reply_markup=keyboard
                            )
                            log.info(f"Sent evening summary to {user_id} (local time: {user_current_time})")
                        except Exception as e:
                            log.warning(f"Failed to send evening summary to {user_id}: {e}")

            # ---- Недельные обзоры (воскресенье в 12:00 по локальному времени пользователя) ----
            weekly_users = await habit_db.get_users_for_weekly_review()
            for user_id in weekly_users:
                # Получаем timezone_offset пользователя
                profile = await habit_db.get_user_profile(user_id)
                if not profile:
                    continue

                timezone_offset = profile.get('timezone_offset', 180)
                user_tz = timezone(timedelta(minutes=timezone_offset))
                user_local_time = now_utc.astimezone(user_tz)
                user_current_time = user_local_time.strftime('%H:%M')
                user_weekday = user_local_time.weekday()

                # Проверяем: воскресенье и 12:00 по локальному времени
                if user_weekday == 6 and user_current_time == "12:00":
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="📈 Посмотреть обзор",
                            web_app={"url": webapp_url("/weekly")}
                        )]
                    ])
                    try:
                        await bot.send_message(
                            user_id,
                            "📊 Недельный обзор готов!\n\n"
                            "Посмотри паттерны и связи за прошедшую неделю.",
                            reply_markup=keyboard
                        )
                        log.info(f"Sent weekly review to {user_id} (local time: {user_current_time})")
                    except Exception as e:
                        log.warning(f"Failed to send weekly review to {user_id}: {e}")

        except Exception as e:
            log.error(f"Notification scheduler error: {e}")

        # Ждём 60 секунд до следующей проверки
        await asyncio.sleep(60)


def start_notification_scheduler(bot):
    """Запустить планировщик уведомлений"""
    asyncio.create_task(notification_scheduler(bot))
    log.info("Notification scheduler task created")
