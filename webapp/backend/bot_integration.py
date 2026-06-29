# webapp/backend/bot_integration.py
# Integration with the main Telegram bot - handlers for food input and notifications

import asyncio
import logging
import os
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

from database import HabitDB
from llm_service import analyze_food_photo, analyze_food_text, generate_daily_summary

log = logging.getLogger("bot_integration")
MSK = timezone(timedelta(hours=3))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # URL где хостится веб-приложение
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


class BotIntegration:
    """
    Класс для интеграции habit tracker с основным Telegram ботом.
    Предоставляет методы для:
    - Обработки фото/текста еды через бота
    - Отправки уведомлений (утренний вопрос о сне, вечерний итог, недельный обзор)
    - Обработки ответов на вопросы о сне
    """

    def __init__(self, db: HabitDB):
        self.db = db
        self.bot_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[dict] = None,
        parse_mode: str = "HTML"
    ) -> bool:
        """Отправить сообщение пользователю"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup

                response = await client.post(
                    f"{self.bot_api_url}/sendMessage",
                    json=payload
                )
                response.raise_for_status()
                return True
        except Exception as e:
            log.error(f"Failed to send message to {chat_id}: {e}")
            return False

    async def download_file(self, file_id: str) -> Optional[bytes]:
        """Скачать файл по file_id"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем путь к файлу
                response = await client.get(
                    f"{self.bot_api_url}/getFile",
                    params={"file_id": file_id}
                )
                response.raise_for_status()
                file_path = response.json()["result"]["file_path"]

                # Скачиваем файл
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                file_response = await client.get(file_url)
                file_response.raise_for_status()
                return file_response.content
        except Exception as e:
            log.error(f"Failed to download file {file_id}: {e}")
            return None

    # ============ Обработка еды через бота ============

    async def handle_food_photo(
        self,
        user_id: int,
        file_id: str,
        caption: Optional[str] = None
    ) -> dict:
        """
        Обработать фото еды, отправленное в бота.
        Сохраняет file_id для последующего отображения в WebApp.
        """
        # Скачиваем фото для анализа
        photo_bytes = await self.download_file(file_id)
        if not photo_bytes:
            return {"success": False, "error": "Не удалось загрузить фото"}

        # Конвертируем в base64 для Vision API
        photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')

        # Анализируем через LLM
        analysis = await analyze_food_photo(photo_base64, caption)

        # Сохраняем в БД
        entry_id = await self.db.add_food_entry(
            user_id=user_id,
            description=analysis.get('description', 'Фото еды'),
            photo_file_id=file_id,
            categories=analysis.get('categories'),
            raw_input=caption,
            source='telegram'
        )

        return {
            "success": True,
            "entry_id": entry_id,
            "analysis": analysis
        }

    async def handle_food_text(self, user_id: int, text: str) -> dict:
        """Обработать текстовое описание еды"""
        # Анализируем через LLM
        analysis = await analyze_food_text(text)

        # Сохраняем в БД
        entry_id = await self.db.add_food_entry(
            user_id=user_id,
            description=analysis.get('description', text),
            categories=analysis.get('categories'),
            raw_input=text,
            source='telegram'
        )

        return {
            "success": True,
            "entry_id": entry_id,
            "analysis": analysis
        }

    # ============ Уведомления ============

    async def send_morning_sleep_question(self, user_id: int) -> bool:
        """Отправить утренний вопрос о сне с inline-кнопками"""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "😴 1", "callback_data": "sleep:1"},
                    {"text": "😕 2", "callback_data": "sleep:2"},
                    {"text": "😐 3", "callback_data": "sleep:3"},
                    {"text": "🙂 4", "callback_data": "sleep:4"},
                    {"text": "😊 5", "callback_data": "sleep:5"},
                ]
            ]
        }

        return await self.send_message(
            user_id,
            "☀️ Доброе утро!\n\nКак ты сегодня спал(а)?",
            reply_markup=keyboard
        )

    async def handle_sleep_callback(self, user_id: int, score: int) -> bool:
        """Обработать ответ на вопрос о сне"""
        success = await self.db.add_sleep_entry(user_id, score)
        if success:
            labels = {
                1: "Очень плохо 😴",
                2: "Плохо 😕",
                3: "Нормально 😐",
                4: "Хорошо 🙂",
                5: "Отлично 😊"
            }
            await self.send_message(
                user_id,
                f"Записал: {labels.get(score, str(score))}. Хорошего дня! ✨"
            )
        return success

    async def send_evening_summary_notification(self, user_id: int) -> bool:
        """Отправить уведомление о готовности вечернего итога"""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📊 Посмотреть итог", "web_app": {"url": webapp_url("/summary")}}
                ]
            ]
        }

        return await self.send_message(
            user_id,
            "🌙 Твой вечерний итог готов!\n\nПосмотри, как прошёл день с точки зрения питания.",
            reply_markup=keyboard
        )

    async def send_weekly_review_notification(self, user_id: int) -> bool:
        """Отправить уведомление о недельном обзоре"""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📈 Посмотреть обзор", "web_app": {"url": webapp_url("/weekly")}}
                ]
            ]
        }

        return await self.send_message(
            user_id,
            "📊 Недельный обзор готов!\n\nПосмотри паттерны и связи за прошедшую неделю.",
            reply_markup=keyboard
        )

    async def send_webapp_button(self, user_id: int) -> bool:
        """Отправить кнопку для открытия WebApp (после оплаты)"""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✨ Открыть ассистент привычек", "web_app": {"url": webapp_url()}}
                ]
            ]
        }

        return await self.send_message(
            user_id,
            "🎉 Теперь тебе доступен ассистент привычек!\n\n"
            "Он поможет освоить полезные привычки:\n"
            "• Food tracker с AI-анализом\n"
            "• Трекер сна\n"
            "• Персональные итоги и обзоры\n\n"
            "Нажми кнопку ниже, чтобы начать:",
            reply_markup=keyboard
        )


# ============ Планировщик уведомлений ============

class NotificationScheduler:
    """
    Планировщик уведомлений.
    Запускается как asyncio task и каждую минуту проверяет,
    нужно ли отправить какие-то уведомления.
    """

    def __init__(self, db: HabitDB, bot: BotIntegration):
        self.db = db
        self.bot = bot
        self._running = False

    async def start(self):
        """Запустить планировщик"""
        self._running = True
        log.info("Notification scheduler started")

        while self._running:
            try:
                await self._check_notifications()
            except Exception as e:
                log.error(f"Notification scheduler error: {e}")

            # Проверяем каждую минуту
            await asyncio.sleep(60)

    def stop(self):
        """Остановить планировщик"""
        self._running = False
        log.info("Notification scheduler stopped")

    async def _check_notifications(self):
        """Проверить и отправить уведомления"""
        now = datetime.now(MSK)
        current_time = now.strftime('%H:%M')
        current_weekday = now.weekday()  # 0 = понедельник, 6 = воскресенье

        # Утренние вопросы о сне
        morning_users = await self.db.get_users_for_notification('morning', current_time)
        for user_id in morning_users:
            # Проверяем, не отвечал ли уже сегодня
            today = now.strftime('%Y-%m-%d')
            existing = await self.db.get_sleep_entry(user_id, today)
            if existing is None:
                await self.bot.send_morning_sleep_question(user_id)
                log.info(f"Sent morning sleep question to {user_id}")

        # Вечерние итоги
        evening_users = await self.db.get_users_for_notification('evening', current_time)
        for user_id in evening_users:
            # Проверяем, есть ли еда за сегодня
            today = now.strftime('%Y-%m-%d')
            food_entries = await self.db.get_food_entries_for_date(user_id, today)
            if food_entries:
                # Генерируем итог если ещё не сгенерирован
                existing_summary = await self.db.get_daily_summary(user_id, today)
                if not existing_summary:
                    profile = await self.db.get_user_profile(user_id)
                    user_goal = profile.get('goal', 'maintain') if profile else 'maintain'
                    summary = await generate_daily_summary(food_entries, user_goal)
                    await self.db.save_daily_summary(user_id, today, summary)

                await self.bot.send_evening_summary_notification(user_id)
                log.info(f"Sent evening summary notification to {user_id}")

        # Недельные обзоры (воскресенье)
        if current_weekday == 6 and current_time == "12:00":  # Воскресенье в 12:00
            weekly_users = await self.db.get_users_for_weekly_review()
            for user_id in weekly_users:
                await self.bot.send_weekly_review_notification(user_id)
                log.info(f"Sent weekly review notification to {user_id}")


# Singleton instances
_bot_integration: Optional[BotIntegration] = None
_scheduler: Optional[NotificationScheduler] = None


async def init_bot_integration(db: HabitDB) -> BotIntegration:
    """Инициализировать интеграцию с ботом"""
    global _bot_integration, _scheduler

    _bot_integration = BotIntegration(db)
    _scheduler = NotificationScheduler(db, _bot_integration)

    # Запускаем планировщик в фоне
    asyncio.create_task(_scheduler.start())

    return _bot_integration


def get_bot_integration() -> Optional[BotIntegration]:
    """Получить экземпляр BotIntegration"""
    return _bot_integration


def get_scheduler() -> Optional[NotificationScheduler]:
    """Получить экземпляр NotificationScheduler"""
    return _scheduler
