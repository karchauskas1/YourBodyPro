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

# YooKassa configuration
YOOKASSA_SHOP_ID = os.getenv("SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("SHOP_SECRET_KEY", "")
MONTH_PRICE = int(os.getenv("MONTH_PRICE", "3690"))
PAID_DAYS = int(os.getenv("PAID_DAYS", "30"))
GRACE_DAYS = int(os.getenv("GRACE_DAYS", "1"))
VAT_CODE = os.getenv("VAT_CODE", "1")
TAX_SYSTEM_CODE = os.getenv("TAX_SYSTEM_CODE", "")
RECEIPT_ITEM_DESCRIPTION = os.getenv("RECEIPT_ITEM_DESCRIPTION", "Подписка YourBody PRO (30 дней)")


# ============ Pydantic Models ============

class OnboardingData(BaseModel):
    goal: str  # 'maintain' | 'lose' | 'gain'
    training_type: str  # 'marathon' | 'own' | 'mixed'
    activity_level: str  # 'active' | 'medium' | 'calm'
    gender: str  # 'male' | 'female'
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
    ate_without_gadgets: Optional[bool] = None


class FoodEntryFeelings(BaseModel):
    hunger_before: Optional[int] = None  # 1-5
    fullness_after: Optional[int] = None  # 1-5


class FoodEntryUpdate(BaseModel):
    description: str


class SleepEntry(BaseModel):
    score: int  # 1-5
    date: Optional[str] = None  # '2025-01-18'


class WorkoutEntry(BaseModel):
    workout_name: str
    duration_minutes: int
    intensity: int  # 1-5
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
    ar_info = await db.get_auto_renewal_info(user['user_id'])
    return {
        "active": is_active,
        "user_id": user['user_id'],
        "auto_renewal_enabled": ar_info["enabled"],
        "has_payment_method": ar_info["has_payment_method"],
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
        'gender': data.gender,
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
        'goal', 'training_type', 'activity_level', 'gender',
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
        fullness_after=data.fullness_after,
        ate_without_gadgets=data.ate_without_gadgets or False
    )

    # Проверяем достижения
    new_achievements = await db.check_achievements(user['user_id'])

    return {
        "success": True,
        "entry_id": entry_id,
        "analysis": analysis,
        "new_achievements": new_achievements,
    }


@app.post("/api/food/photo")
async def add_food_photo(
    photo: UploadFile = File(...),
    context: str = Form(default=""),
    time: Optional[str] = Form(default=None),
    hunger_before: Optional[int] = Form(default=None),
    fullness_after: Optional[int] = Form(default=None),
    ate_without_gadgets: Optional[str] = Form(default=None),
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
            fullness_after=fullness_after,
            ate_without_gadgets=ate_without_gadgets == 'true' if ate_without_gadgets else False
        )

        # Проверяем достижения
        new_achievements = await db.check_achievements(user['user_id'])

        return {
            "success": True,
            "entry_id": entry_id,
            "analysis": analysis,
            "new_achievements": new_achievements,
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


@app.patch("/api/food/{entry_id}")
async def update_food_entry(
    entry_id: int,
    data: FoodEntryUpdate,
    user: Dict = Depends(get_current_user)
):
    """Обновить описание приема пищи"""
    if not data.description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    updated = await db.update_food_entry_description(
        entry_id=entry_id,
        user_id=user['user_id'],
        description=data.description.strip()
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
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
    new_achievements = await db.check_achievements(user['user_id'])
    return {"success": success, "new_achievements": new_achievements}


# --- Workout Tracker ---

@app.post("/api/workouts")
async def add_workout(
    data: WorkoutEntry,
    user: Dict = Depends(get_current_user)
):
    """Добавить тренировку"""
    if not 1 <= data.intensity <= 5:
        raise HTTPException(status_code=400, detail="Intensity must be 1-5")

    if data.duration_minutes <= 0:
        raise HTTPException(status_code=400, detail="Duration must be positive")

    workout_id = await db.add_workout_entry(
        user['user_id'],
        data.workout_name,
        data.duration_minutes,
        data.intensity,
        data.date
    )
    new_achievements = await db.check_achievements(user['user_id'])
    return {"success": True, "workout_id": workout_id, "new_achievements": new_achievements}


@app.get("/api/workouts/{date}")
async def get_workouts_by_date(
    date: str,
    user: Dict = Depends(get_current_user)
):
    """Получить тренировки за определенную дату"""
    workouts = await db.get_workout_entries_for_date(user['user_id'], date)
    return {"date": date, "workouts": workouts}


@app.delete("/api/workouts/{workout_id}")
async def delete_workout(
    workout_id: int,
    user: Dict = Depends(get_current_user)
):
    """Удалить тренировку"""
    deleted = await db.delete_workout_entry(user['user_id'], workout_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"success": True}


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
    user_gender = profile.get('gender') if profile else None
    user_activity_level = profile.get('activity_level') if profile else None

    # Получаем тренировки за сегодня
    workouts = await db.get_workout_entries_for_date(user['user_id'], today)

    # Получаем оценку сна за сегодня
    sleep_entry = await db.get_sleep_entry_for_date(user['user_id'], today)
    sleep_score = sleep_entry.get('score') if sleep_entry else None

    # Генерируем итог с учетом всех факторов
    summary = await generate_daily_summary(
        food_entries,
        user_goal,
        user_gender=user_gender,
        user_activity_level=user_activity_level,
        workouts=workouts,
        sleep_score=sleep_score
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
        user_gender = profile.get('gender') if profile else None
        user_activity_level = profile.get('activity_level') if profile else None

        workouts = await db.get_workout_entries_for_date(user['user_id'], date)

        # Получаем оценку сна за эту дату
        sleep_entry = await db.get_sleep_entry_for_date(user['user_id'], date)
        sleep_score = sleep_entry.get('score') if sleep_entry else None

        summary = await generate_daily_summary(
            food_entries,
            user_goal,
            user_gender=user_gender,
            user_activity_level=user_activity_level,
            workouts=workouts,
            sleep_score=sleep_score
        )
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
    user_gender = profile.get('gender') if profile else None
    user_activity_level = profile.get('activity_level') if profile else None

    # Получаем тренировки за сегодня
    workouts = await db.get_workout_entries_for_date(user['user_id'], today)

    # Получаем оценку сна за сегодня
    sleep_entry = await db.get_sleep_entry_for_date(user['user_id'], today)
    sleep_score = sleep_entry.get('score') if sleep_entry else None

    # Генерируем новый итог с учетом всех факторов
    summary = await generate_daily_summary(
        food_entries,
        user_goal,
        user_gender=user_gender,
        user_activity_level=user_activity_level,
        workouts=workouts,
        sleep_score=sleep_score
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
    workout_data = await db.get_workout_entries_for_week(user['user_id'], week_start)

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
    user_gender = profile.get('gender') if profile else None
    user_activity_level = profile.get('activity_level') if profile else None

    # Генерируем умный обзор с паттернами
    summary = await generate_weekly_summary(
        food_data,
        sleep_data,
        workout_data,
        user_goal,
        user_gender=user_gender,
        user_activity_level=user_activity_level
    )

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
        workout_data = await db.get_workout_entries_for_week(user['user_id'], week_start)

        has_data = any(food_data.values()) or any(v is not None for v in sleep_data.values())
        if not has_data:
            return {"week_start": week_start, "summary": None}

        profile = await db.get_user_profile(user['user_id'])
        user_goal = profile.get('goal', 'maintain') if profile else 'maintain'
        user_gender = profile.get('gender') if profile else None
        user_activity_level = profile.get('activity_level') if profile else None

        summary = await generate_weekly_summary(
            food_data,
            sleep_data,
            workout_data,
            user_goal,
            user_gender=user_gender,
            user_activity_level=user_activity_level
        )
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
    streak = await db.get_food_streak(user['user_id'])

    return {
        "date": today,
        "profile": profile,
        "streak": streak,
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


@app.post("/api/payment/create")
async def create_payment(
    user: Dict = Depends(get_current_user_optional)
):
    """Создать платёж YooKassa для подписки"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        import uuid
        import requests
        from requests.auth import HTTPBasicAuth

        user_id = user['user_id']
        username = user.get('username', '')

        # Получаем телефон пользователя из БД
        phone = await db.get_user_phone(user_id)

        # Генерируем уникальный ID платежа
        idempotence_key = str(uuid.uuid4())

        # Описание платежа с данными пользователя (как в боте)
        description = f"{RECEIPT_ITEM_DESCRIPTION}, user_id={user_id}"
        if phone:
            description += f", phone={phone}"
        if username:
            description += f", @{username}"

        # Создаём платёж через YooKassa API
        url = "https://api.yookassa.ru/v3/payments"
        headers = {
            "Idempotence-Key": idempotence_key,
            "Content-Type": "application/json"
        }

        # Проверяем реферальную скидку
        referral_reward = await db.get_unused_referral_reward(user_id)
        actual_price = MONTH_PRICE
        if referral_reward:
            discount_pct = referral_reward["discount_percent"]
            discount_amount = MONTH_PRICE * discount_pct // 100
            actual_price = MONTH_PRICE - discount_amount
            await db.use_referral_reward(referral_reward["id"])
            print(f"User {user_id} using referral discount {discount_pct}% — price {MONTH_PRICE} -> {actual_price}")

        payload = {
            "amount": {
                "value": f"{actual_price}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": os.getenv("WEBAPP_URL", "https://yourbody.app")
            },
            "capture": True,
            "save_payment_method": True,
            "description": description,
            "metadata": {
                "user_id": str(user_id),
                "username": username,
                "phone": phone or "",
                "source": "webapp"
            }
        }

        # Добавляем чек (receipt) если есть телефон
        if phone:
            receipt = {
                "customer": {"phone": phone},
                "items": [{
                    "description": RECEIPT_ITEM_DESCRIPTION,
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{actual_price}.00",
                        "currency": "RUB"
                    },
                    "vat_code": int(VAT_CODE)
                }]
            }
            if TAX_SYSTEM_CODE:
                try:
                    receipt["tax_system_code"] = int(TAX_SYSTEM_CODE)
                except ValueError:
                    pass
            payload["receipt"] = receipt

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            timeout=10
        )

        if response.status_code != 200:
            print(f"YooKassa API error: {response.status_code} {response.text}")
            raise HTTPException(
                status_code=500,
                detail="Failed to create payment"
            )

        payment_data = response.json()
        confirmation_url = payment_data.get("confirmation", {}).get("confirmation_url")

        if not confirmation_url:
            raise HTTPException(
                status_code=500,
                detail="No confirmation URL in payment response"
            )

        # Сохраняем платёж в БД
        await db.save_payment(user_id, payment_data["id"], MONTH_PRICE, payment_data.get("status", "pending"))

        return {
            "payment_id": payment_data["id"],
            "confirmation_url": confirmation_url,
            "amount": MONTH_PRICE
        }

    except requests.RequestException as e:
        print(f"Payment creation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Payment service error: {str(e)}"
        )


@app.post("/api/payment/check")
async def check_payment(
    user: Dict = Depends(get_current_user_optional)
):
    """Проверить статус платежа и активировать подписку если оплачен"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        import requests
        from requests.auth import HTTPBasicAuth

        user_id = user['user_id']

        # Получаем payment_id из тела запроса
        # Но для безопасности проверяем все pending платежи пользователя
        body = {}
        payment_id = None

        # Если передан payment_id — проверяем конкретный
        # Иначе — ищем последний pending платёж пользователя
        # (payment_id может прийти через query или body)

        # Проверяем через YooKassa API — ищем все платежи с metadata.user_id
        url = "https://api.yookassa.ru/v3/payments"
        response = requests.get(
            url,
            params={
                "status": "succeeded",
                "limit": 10,
            },
            auth=HTTPBasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            timeout=10
        )

        if response.status_code != 200:
            print(f"YooKassa list error: {response.status_code} {response.text}")
            raise HTTPException(status_code=500, detail="Failed to check payments")

        data = response.json()
        items = data.get("items", [])

        # Ищем успешный платёж для этого пользователя
        found_payment = None
        for item in items:
            metadata = item.get("metadata", {})
            meta_user_id = metadata.get("user_id")
            if meta_user_id and str(meta_user_id) == str(user_id):
                found_payment = item
                break

        if found_payment:
            # Платёж найден! Активируем подписку
            payment_id = found_payment["id"]
            await db.update_payment_status(payment_id, "succeeded")
            new_expires = await db.activate_subscription(user_id, PAID_DAYS, GRACE_DAYS)

            # Сохраняем способ оплаты для автопродления
            pm = found_payment.get("payment_method", {})
            if pm.get("saved") and pm.get("id"):
                await db.set_payment_method(user_id, pm["id"])
                print(f"Payment method {pm['id']} saved for user {user_id}")

            # Обработка реферала (mark_referral_paid создаёт reward автоматически)
            try:
                referrer_id = await db.mark_referral_paid(user_id)
                if referrer_id:
                    print(f"Referral reward granted to user {referrer_id} for referred {user_id}")
            except Exception as e:
                print(f"Referral reward error for user {user_id}: {e}")

            print(f"Subscription activated via webapp for user {user_id}, payment {payment_id}, expires_at={new_expires}")

            return {
                "status": "succeeded",
                "payment_id": payment_id,
                "subscription_active": True,
                "expires_at": new_expires
            }

        # Не нашли — подписка не активирована
        return {
            "status": "pending",
            "subscription_active": False,
            "message": "Платёж ещё не обработан. Попробуйте через несколько секунд."
        }

    except requests.RequestException as e:
        print(f"Payment check error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Payment check error: {str(e)}"
        )


# ============ Autorenewal API ============

@app.get("/api/autorenewal")
async def get_autorenewal_status(user: Dict = Depends(get_current_user)):
    """Получить статус автопродления"""
    info = await db.get_auto_renewal_info(user['user_id'])
    return info


@app.post("/api/autorenewal/toggle")
async def toggle_autorenewal(user: Dict = Depends(get_current_user)):
    """Включить/выключить автопродление"""
    info = await db.get_auto_renewal_info(user['user_id'])
    new_state = not info["enabled"]
    await db.set_auto_renewal(user['user_id'], new_state)
    return {"enabled": new_state}


# ============ Referral API ============

import string as _string
import secrets as _secrets

def _generate_ref_code(length: int = 6) -> str:
    chars = _string.ascii_uppercase + _string.digits
    return ''.join(_secrets.choice(chars) for _ in range(length))


@app.get("/api/referral")
async def get_referral_info(user: Dict = Depends(get_current_user)):
    """Получить реферальную ссылку и статистику"""
    user_id = user['user_id']

    # Генерируем код если нет
    code = await db.get_referral_code(user_id)
    if not code:
        for _ in range(10):
            code = _generate_ref_code()
            existing = await db.find_user_by_referral_code(code)
            if not existing:
                break
        await db.set_referral_code(user_id, code)

    stats = await db.get_referral_stats(user_id)
    bot_username = os.getenv("BOT_USERNAME", "YourBodyPet_bot")
    ref_link = f"https://t.me/{bot_username}?start=ref_{code}"

    return {
        "code": code,
        "link": ref_link,
        "stats": stats,
    }


# ============ Gamification API ============

@app.get("/api/streak")
async def get_streak(user: Dict = Depends(get_current_user)):
    """Получить стрик питания"""
    streak = await db.get_food_streak(user['user_id'])
    return streak


ACHIEVEMENTS_CATALOG = [
    {"id": "first_food", "name": "Первый шаг", "description": "Первый лог еды", "icon": "\ud83c\udf31"},
    {"id": "streak_7", "name": "Неделя", "description": "7-дневный стрик еды", "icon": "\ud83d\udd25"},
    {"id": "streak_30", "name": "Месяц", "description": "30-дневный стрик еды", "icon": "\ud83d\udcaa"},
    {"id": "sleep_7", "name": "Мастер сна", "description": "7 дней сна подряд", "icon": "\ud83d\ude34"},
    {"id": "workouts_10", "name": "Спортсмен", "description": "10 тренировок всего", "icon": "\ud83c\udfcb\ufe0f"},
    {"id": "workouts_30", "name": "Марафонец", "description": "30 тренировок", "icon": "\ud83c\udfc5"},
    {"id": "mindful_10", "name": "Осознанность", "description": "10 приёмов пищи без гаджетов", "icon": "\ud83e\uddd8"},
    {"id": "weekly_first", "name": "Полная картина", "description": "Первый недельный обзор", "icon": "\ud83d\udcca"},
]

@app.get("/api/achievements")
async def get_achievements(user: Dict = Depends(get_current_user)):
    """Получить список достижений"""
    unlocked_ids = await db.get_user_achievements(user['user_id'])

    # Get unlock timestamps
    unlocked_map = {}
    cur = await db.conn.execute(
        "SELECT achievement_id, unlocked_at FROM user_achievements WHERE user_id=?",
        (user['user_id'],)
    )
    for row in await cur.fetchall():
        unlocked_map[row[0]] = row[1]

    result = []
    for a in ACHIEVEMENTS_CATALOG:
        unlocked = a["id"] in unlocked_ids
        entry = {**a, "unlocked": unlocked}
        if unlocked and unlocked_map.get(a["id"]):
            entry["unlocked_at"] = datetime.fromtimestamp(
                unlocked_map[a["id"]], timezone.utc
            ).isoformat()
        result.append(entry)

    return {"achievements": result}


# ============ Admin Analytics API ============

ADMIN_IDS_ENV = os.getenv("ADMIN_IDS", "")
ADMIN_IDS_SET = {int(x) for x in ADMIN_IDS_ENV.replace(",", " ").split() if x.strip().isdigit()}


@app.get("/api/admin/stats")
async def get_admin_stats(user: Dict = Depends(get_current_user)):
    """Админ-дашборд с метриками"""
    user_id = user['user_id']
    if ADMIN_IDS_SET and user_id not in ADMIN_IDS_SET:
        raise HTTPException(status_code=403, detail="Access denied")

    total_users = await db.count_total_users()
    active_users = await db.count_active_users()
    new_7d = await db.count_new_users(7)
    new_30d = await db.count_new_users(30)
    revenue_month = await db.sum_revenue(30)
    revenue_total = await db.total_revenue()
    cancel_reasons = await db.get_cancellation_reasons_breakdown()
    daily_users = await db.get_daily_new_users(30)
    daily_revenue = await db.get_daily_revenue(30)
    feature_stats = await db.get_feature_usage_stats()
    avg_food = await db.get_avg_food_entries_per_day()
    auto_renewal_count = await db.get_auto_renewal_count()
    referral_stats = await db.get_referral_stats_admin()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "expired": total_users - active_users,
            "new_7d": new_7d,
            "new_30d": new_30d,
        },
        "revenue": {
            "month": revenue_month,
            "total": revenue_total,
        },
        "conversion": {
            "paid_total": active_users,
            "started_total": total_users,
            "rate": round(active_users / total_users, 2) if total_users > 0 else 0,
        },
        "churn": {
            "reasons": cancel_reasons,
        },
        "engagement": {
            "avg_food_per_day": avg_food,
            "features": feature_stats,
        },
        "retention": {
            "auto_renewal_count": auto_renewal_count,
            "auto_renewal_pct": round(auto_renewal_count / active_users, 2) if active_users > 0 else 0,
        },
        "charts": {
            "daily_users": daily_users,
            "daily_revenue": daily_revenue,
        },
        "referrals": referral_stats,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
