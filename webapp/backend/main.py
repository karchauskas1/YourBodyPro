# webapp/backend/main.py
# FastAPI backend для Habit Tracker WebApp

import os
import hashlib
import hmac
import json
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from database import db, HabitDB
from llm_service import (
    analyze_food_photo,
    analyze_food_text,
    generate_daily_summary,
    generate_weekly_summary
)

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MSK = timezone(timedelta(hours=3))


# ============ Pydantic Models ============

class OnboardingData(BaseModel):
    goal: str  # 'maintain' | 'lose' | 'gain'
    training_type: str  # 'marathon' | 'own' | 'mixed'
    activity_level: str  # 'active' | 'medium' | 'calm'
    food_tracker_enabled: bool = False
    sleep_tracker_enabled: bool = False
    weekly_review_enabled: bool = False
    evening_summary_time: str = "21:00"
    morning_question_time: str = "08:00"


class FoodEntryText(BaseModel):
    text: str
    time: Optional[str] = None  # Формат 'HH:MM'
    hunger_before: Optional[int] = None  # 1-5
    fullness_after: Optional[int] = None  # 1-5


class FoodEntryFeelings(BaseModel):
    hunger_before: Optional[int] = None  # 1-5
    fullness_after: Optional[int] = None  # 1-5


class SleepEntry(BaseModel):
    score: int  # 1-5
    date: Optional[str] = None  # '2025-01-18'


class UserProfile(BaseModel):
    user_id: int
    goal: Optional[str] = None
    training_type: Optional[str] = None
    activity_level: Optional[str] = None
    food_tracker_enabled: bool = False
    sleep_tracker_enabled: bool = False
    weekly_review_enabled: bool = False
    evening_summary_time: str = "21:00"
    morning_question_time: str = "08:00"
    onboarding_completed: bool = False


# ============ Auth ============

def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Валидация initData от Telegram WebApp
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))

        if 'hash' not in parsed:
            return None

        received_hash = parsed.pop('hash')

        # Сортируем и формируем data-check-string
        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        # Создаём secret_key
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()

        # Вычисляем hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if calculated_hash != received_hash:
            return None

        # Проверяем auth_date (не старше 24 часов)
        auth_date = int(parsed.get('auth_date', 0))
        if datetime.now(timezone.utc).timestamp() - auth_date > 86400:
            return None

        # Парсим user
        user_data = json.loads(parsed.get('user', '{}'))
        return {
            'user_id': user_data.get('id'),
            'username': user_data.get('username'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name'),
            'language_code': user_data.get('language_code'),
            'auth_date': auth_date
        }

    except Exception as e:
        print(f"Auth validation error: {e}")
        return None


async def get_current_user(
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data")
) -> Dict[str, Any]:
    """Dependency для получения текущего пользователя из заголовка"""

    # Для разработки: если нет init_data, используем тестового пользователя
    if not x_telegram_init_data:
        # В продакшене это должно возвращать ошибку
        if os.getenv("DEBUG", "false").lower() == "true":
            return {
                'user_id': 123456789,
                'username': 'test_user',
                'first_name': 'Test',
                'last_name': 'User'
            }
        raise HTTPException(status_code=401, detail="Missing Telegram init data")

    user_data = validate_telegram_init_data(x_telegram_init_data, BOT_TOKEN)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid Telegram init data")

    # Проверяем подписку
    is_active = await db.is_subscription_active(user_data['user_id'])
    if not is_active:
        raise HTTPException(
            status_code=403,
            detail="Subscription required",
            headers={"X-Subscription-Status": "inactive"}
        )

    return user_data


async def get_current_user_optional(
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data")
) -> Optional[Dict[str, Any]]:
    """Dependency без проверки подписки (для страницы оплаты)"""
    if not x_telegram_init_data:
        if os.getenv("DEBUG", "false").lower() == "true":
            return {
                'user_id': 123456789,
                'username': 'test_user',
                'first_name': 'Test'
            }
        return None

    return validate_telegram_init_data(x_telegram_init_data, BOT_TOKEN)


# ============ App Lifecycle ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db.db_path = os.path.join(os.path.dirname(__file__), '../../bot.db')
    await db.connect()
    await db.init_schema()
    print("Database connected and schema initialized")
    yield
    # Shutdown
    await db.close()
    print("Database connection closed")


# ============ FastAPI App ============

app = FastAPI(
    title="YourBody Habit Tracker API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS для Telegram WebApp
ALLOWED_ORIGINS = [
    "https://your-body-pro.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Routes ============

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(MSK).isoformat()}


# --- Auth & Profile ---

@app.get("/api/me")
async def get_me(user: Dict = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    profile = await db.get_user_profile(user['user_id'])
    return {
        "user": user,
        "profile": profile,
        "subscription_active": True  # Если дошли сюда, значит подписка активна
    }


@app.get("/api/subscription-status")
async def get_subscription_status(
    user: Dict = Depends(get_current_user_optional)
):
    """Проверить статус подписки (без требования активной подписки)"""
    if not user:
        return {"active": False, "reason": "not_authenticated"}

    is_active = await db.is_subscription_active(user['user_id'])
    return {
        "active": is_active,
        "user_id": user['user_id']
    }


# --- Onboarding ---

@app.get("/api/onboarding")
async def get_onboarding(user: Dict = Depends(get_current_user)):
    """Получить данные онбординга"""
    profile = await db.get_user_profile(user['user_id'])
    return profile or {}


@app.post("/api/onboarding")
async def save_onboarding(
    data: OnboardingData,
    user: Dict = Depends(get_current_user)
):
    """Сохранить данные онбординга"""
    await db.upsert_user_profile(user['user_id'], {
        'goal': data.goal,
        'training_type': data.training_type,
        'activity_level': data.activity_level,
        'food_tracker_enabled': 1 if data.food_tracker_enabled else 0,
        'sleep_tracker_enabled': 1 if data.sleep_tracker_enabled else 0,
        'weekly_review_enabled': 1 if data.weekly_review_enabled else 0,
        'evening_summary_time': data.evening_summary_time,
        'morning_question_time': data.morning_question_time,
        'onboarding_completed': 1
    })
    return {"success": True}


@app.patch("/api/settings")
async def update_settings(
    data: Dict[str, Any],
    user: Dict = Depends(get_current_user)
):
    """Обновить отдельные настройки"""
    allowed_fields = {
        'goal', 'training_type', 'activity_level',
        'food_tracker_enabled', 'sleep_tracker_enabled', 'weekly_review_enabled',
        'evening_summary_time', 'morning_question_time'
    }

    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    # Конвертируем bool в int для SQLite
    for key in ['food_tracker_enabled', 'sleep_tracker_enabled', 'weekly_review_enabled']:
        if key in update_data:
            update_data[key] = 1 if update_data[key] else 0

    if update_data:
        await db.upsert_user_profile(user['user_id'], update_data)

    return {"success": True}


# --- Food Tracker ---

@app.get("/api/food/today")
async def get_today_food(user: Dict = Depends(get_current_user)):
    """Получить еду за сегодня"""
    today = datetime.now(MSK).strftime('%Y-%m-%d')
    entries = await db.get_food_entries_for_date(user['user_id'], today)
    return {"date": today, "entries": entries}


@app.get("/api/food/{date}")
async def get_food_by_date(date: str, user: Dict = Depends(get_current_user)):
    """Получить еду за конкретную дату"""
    entries = await db.get_food_entries_for_date(user['user_id'], date)
    return {"date": date, "entries": entries}


@app.post("/api/food/text")
async def add_food_text(
    data: FoodEntryText,
    user: Dict = Depends(get_current_user)
):
    """Добавить еду текстом"""
    # Анализируем текст через LLM
    analysis = await analyze_food_text(data.text)

    # Сохраняем в БД
    entry_id = await db.add_food_entry(
        user_id=user['user_id'],
        description=analysis.get('description', data.text),
        categories=analysis.get('categories'),
        raw_input=data.text,
        source='webapp',
        custom_time=data.time,
        hunger_before=data.hunger_before,
        fullness_after=data.fullness_after
    )

    return {
        "success": True,
        "entry_id": entry_id,
        "analysis": analysis
    }


@app.post("/api/food/photo")
async def add_food_photo(
    photo: UploadFile = File(...),
    context: str = Form(default=""),
    time: Optional[str] = Form(default=None),
    hunger_before: Optional[int] = Form(default=None),
    fullness_after: Optional[int] = Form(default=None),
    user: Dict = Depends(get_current_user)
):
    """Добавить еду фото"""
    try:
        # Читаем и конвертируем в base64
        contents = await photo.read()

        # Проверяем размер (макс 10MB)
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Фото слишком большое (макс 10MB)")

        photo_base64 = base64.b64encode(contents).decode('utf-8')

        # Анализируем через Vision API
        analysis = await analyze_food_photo(photo_base64, context or None)

        # Проверяем на ошибку анализа
        if analysis.get('error'):
            print(f"LLM analysis error: {analysis.get('error')}")
            # Всё равно сохраняем, но с базовым описанием
            analysis['description'] = analysis.get('description', 'Фото еды')

        # Примечание: photo_file_id будет заполнен при загрузке через Telegram бота
        # Здесь мы сохраняем без file_id (можно добавить локальное хранение)

        entry_id = await db.add_food_entry(
            user_id=user['user_id'],
            description=analysis.get('description', 'Фото еды'),
            categories=analysis.get('categories'),
            raw_input=context,
            source='webapp',
            custom_time=time,
            hunger_before=hunger_before,
            fullness_after=fullness_after
        )

        return {
            "success": True,
            "entry_id": entry_id,
            "analysis": analysis
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in add_food_photo: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении: {str(e)}")


@app.delete("/api/food/{entry_id}")
async def delete_food_entry(
    entry_id: int,
    user: Dict = Depends(get_current_user)
):
    """Удалить запись о еде"""
    deleted = await db.delete_food_entry(user['user_id'], entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"success": True}


@app.patch("/api/food/{entry_id}/feelings")
async def update_food_entry_feelings(
    entry_id: int,
    data: FoodEntryFeelings,
    user: Dict = Depends(get_current_user)
):
    """Обновить оценки голода и сытости для существующей записи"""
    updated = await db.update_food_entry_feelings(
        entry_id=entry_id,
        user_id=user['user_id'],
        hunger_before=data.hunger_before,
        fullness_after=data.fullness_after
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found or nothing to update")
    return {"success": True}


@app.get("/api/food/calendar/{year}/{month}")
async def get_food_calendar(
    year: int,
    month: int,
    user: Dict = Depends(get_current_user)
):
    """Получить данные о питании за месяц для календаря"""
    # Определяем начало и конец месяца
    start_date = datetime(year, month, 1, tzinfo=MSK)
    if month == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=MSK) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1, tzinfo=MSK) - timedelta(days=1)

    # Получаем все записи за месяц
    days_data = {}
    current = start_date
    while current <= end_date:
        date_str = current.strftime('%Y-%m-%d')
        entries = await db.get_food_entries_for_date(user['user_id'], date_str)
        if entries:
            days_data[date_str] = {
                'count': len(entries),
                'entries': entries
            }
        current += timedelta(days=1)

    return {
        'year': year,
        'month': month,
        'days': days_data
    }


# --- Sleep Tracker ---

@app.get("/api/sleep/today")
async def get_today_sleep(user: Dict = Depends(get_current_user)):
    """Получить оценку сна за сегодня"""
    today = datetime.now(MSK).strftime('%Y-%m-%d')
    score = await db.get_sleep_entry(user['user_id'], today)
    return {"date": today, "score": score}


@app.post("/api/sleep")
async def add_sleep_entry(
    data: SleepEntry,
    user: Dict = Depends(get_current_user)
):
    """Добавить оценку сна"""
    if not 1 <= data.score <= 5:
        raise HTTPException(status_code=400, detail="Score must be 1-5")

    success = await db.add_sleep_entry(
        user['user_id'],
        data.score,
        data.date
    )
    return {"success": success}


# --- Daily Summary ---

@app.get("/api/summary/today")
async def get_today_summary(user: Dict = Depends(get_current_user)):
    """Получить или сгенерировать итог за сегодня"""
    today = datetime.now(MSK).strftime('%Y-%m-%d')

    # Проверяем, есть ли уже сгенерированный итог
    existing = await db.get_daily_summary(user['user_id'], today)
    if existing:
        return {"date": today, "summary": existing, "cached": True}

    # Получаем еду за сегодня
    food_entries = await db.get_food_entries_for_date(user['user_id'], today)

    if not food_entries:
        return {
            "date": today,
            "summary": None,
            "message": "Нет записей о еде за сегодня"
        }

    # Получаем профиль пользователя
    profile = await db.get_user_profile(user['user_id'])
    user_goal = profile.get('goal', 'maintain') if profile else 'maintain'

    # Генерируем итог
    summary = await generate_daily_summary(
        food_entries,
        user_goal,
        has_training_today=False  # TODO: интеграция с календарём тренировок
    )

    # Сохраняем
    await db.save_daily_summary(user['user_id'], today, summary)

    return {"date": today, "summary": summary, "cached": False}


@app.get("/api/summary/{date}")
async def get_summary_by_date(
    date: str,
    user: Dict = Depends(get_current_user)
):
    """Получить итог за конкретную дату"""
    summary = await db.get_daily_summary(user['user_id'], date)

    if not summary:
        # Пытаемся сгенерировать
        food_entries = await db.get_food_entries_for_date(user['user_id'], date)
        if not food_entries:
            return {"date": date, "summary": None}

        profile = await db.get_user_profile(user['user_id'])
        user_goal = profile.get('goal', 'maintain') if profile else 'maintain'

        summary = await generate_daily_summary(food_entries, user_goal)
        await db.save_daily_summary(user['user_id'], date, summary)

    return {"date": date, "summary": summary}


@app.post("/api/summary/recalculate")
async def recalculate_summary(user: Dict = Depends(get_current_user)):
    """Принудительно пересчитать итог за сегодня"""
    today = datetime.now(MSK).strftime('%Y-%m-%d')

    # Получаем еду за сегодня
    food_entries = await db.get_food_entries_for_date(user['user_id'], today)

    if not food_entries:
        return {
            "date": today,
            "summary": None,
            "message": "Нет записей о еде за сегодня"
        }

    # Получаем профиль пользователя
    profile = await db.get_user_profile(user['user_id'])
    user_goal = profile.get('goal', 'maintain') if profile else 'maintain'

    # Генерируем новый итог
    summary = await generate_daily_summary(
        food_entries,
        user_goal,
        has_training_today=False
    )

    # Перезаписываем в БД
    await db.save_daily_summary(user['user_id'], today, summary)

    return {"date": today, "summary": summary, "recalculated": True}


# --- Weekly Summary ---

def get_week_start(date: datetime) -> str:
    """Получить понедельник недели"""
    monday = date - timedelta(days=date.weekday())
    return monday.strftime('%Y-%m-%d')


@app.get("/api/weekly/current")
async def get_current_weekly(user: Dict = Depends(get_current_user)):
    """Получить недельный обзор за текущую неделю"""
    now = datetime.now(MSK)
    week_start = get_week_start(now)

    # Проверяем кэш
    existing = await db.get_weekly_summary(user['user_id'], week_start)
    if existing:
        return {"week_start": week_start, "summary": existing, "cached": True}

    # Собираем данные за неделю
    food_data = await db.get_food_entries_for_week(user['user_id'], week_start)
    sleep_data = await db.get_sleep_entries_for_week(user['user_id'], week_start)

    # Проверяем, есть ли данные
    has_data = any(food_data.values()) or any(v is not None for v in sleep_data.values())
    if not has_data:
        return {
            "week_start": week_start,
            "summary": None,
            "message": "Недостаточно данных за неделю"
        }

    # Получаем профиль
    profile = await db.get_user_profile(user['user_id'])
    user_goal = profile.get('goal', 'maintain') if profile else 'maintain'

    # Генерируем обзор
    summary = await generate_weekly_summary(food_data, sleep_data, user_goal)

    # Сохраняем
    await db.save_weekly_summary(user['user_id'], week_start, summary)

    return {"week_start": week_start, "summary": summary, "cached": False}


@app.get("/api/weekly/{week_start}")
async def get_weekly_by_date(
    week_start: str,
    user: Dict = Depends(get_current_user)
):
    """Получить недельный обзор за конкретную неделю"""
    summary = await db.get_weekly_summary(user['user_id'], week_start)

    if not summary:
        food_data = await db.get_food_entries_for_week(user['user_id'], week_start)
        sleep_data = await db.get_sleep_entries_for_week(user['user_id'], week_start)

        has_data = any(food_data.values()) or any(v is not None for v in sleep_data.values())
        if not has_data:
            return {"week_start": week_start, "summary": None}

        profile = await db.get_user_profile(user['user_id'])
        user_goal = profile.get('goal', 'maintain') if profile else 'maintain'

        summary = await generate_weekly_summary(food_data, sleep_data, user_goal)
        await db.save_weekly_summary(user['user_id'], week_start, summary)

    return {"week_start": week_start, "summary": summary}


# --- Dashboard ---

@app.get("/api/dashboard")
async def get_dashboard(user: Dict = Depends(get_current_user)):
    """Получить данные для главного экрана"""
    today = datetime.now(MSK).strftime('%Y-%m-%d')

    profile = await db.get_user_profile(user['user_id'])
    food_entries = await db.get_food_entries_for_date(user['user_id'], today)
    sleep_score = await db.get_sleep_entry(user['user_id'], today)
    daily_summary = await db.get_daily_summary(user['user_id'], today)

    return {
        "date": today,
        "profile": profile,
        "food": {
            "entries": food_entries,
            "count": len(food_entries)
        },
        "sleep": {
            "score": sleep_score
        },
        "summary": {
            "available": daily_summary is not None,
            "data": daily_summary
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
