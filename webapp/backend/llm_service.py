# webapp/backend/llm_service.py
# Интеграция с OpenRouter для анализа еды и генерации итогов

import httpx
import base64
import json
import os
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Модели
VISION_MODEL = "openai/gpt-4o"  # для анализа фото
TEXT_MODEL = "openai/gpt-4o-mini"  # для текстового анализа (дешевле)


# Структурные модели питания (для промптов)
NUTRITION_MODELS = {
    "maintain": {
        "proteins": "20-25%",
        "fats": "25-30%",
        "carbs": "45-55%",
        "note": "основа углеводов — медленные, овощи ежедневно"
    },
    "lose": {
        "proteins": "25-30%",
        "fats": "20-25%",
        "carbs": "35-45%",
        "note": "акцент на медленные углеводы и овощи, быстрые допустимы но не доминируют"
    },
    "gain": {
        "proteins": "20-25%",
        "fats": "25-30%",
        "carbs": "50-60%",
        "note": "допускается больше быстрых углеводов при сохранении разнообразия"
    }
}

FOOD_CATEGORIES = """
Категории продуктов:
- Белки животные: мясо, рыба, яйца, морепродукты, молочные продукты
- Белки растительные: бобовые, тофу, темпе, орехи, семена
- Жиры: масла, орехи, авокадо, жирная рыба, сливочное масло
- Углеводы медленные: крупы, цельнозерновой хлеб, макароны из твёрдых сортов, бобовые, овощи
- Углеводы быстрые: сахар, сладости, белый хлеб, выпечка, фрукты, мёд, соки
- Овощи и клетчатка: все овощи, зелень, грибы
"""


async def analyze_food_photo(
    photo_base64: str,
    user_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Анализ фото еды через Vision API
    Возвращает: описание продуктов и их категории
    """
    # Проверяем наличие API ключа
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        return {
            "description": "Фото еды",
            "products": [],
            "categories": {},
            "error": "API key not configured"
        }

    system_prompt = f"""Ты эксперт по питанию. Проанализируй фото еды и верни JSON.

{FOOD_CATEGORIES}

Твоя задача:
1. Определить все продукты на фото
2. Классифицировать их по категориям
3. НЕ считать калории и БЖУ в граммах
4. Описать кратко и по-человечески

Верни ТОЛЬКО JSON в формате:
{{
    "description": "краткое описание (например: 'Овсянка с ягодами и орехами')",
    "products": ["овсянка", "черника", "грецкие орехи", "мёд"],
    "categories": {{
        "proteins_animal": [],
        "proteins_plant": ["грецкие орехи"],
        "fats": ["грецкие орехи"],
        "carbs_slow": ["овсянка"],
        "carbs_fast": ["мёд", "черника"],
        "vegetables": []
    }}
}}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{photo_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": user_context or "Что на этом фото?"
                }
            ]
        }
    ]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": VISION_MODEL,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.3
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Парсим JSON из ответа
            # Убираем возможные markdown-блоки
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            return json.loads(content)

    except Exception as e:
        return {
            "description": "Не удалось распознать",
            "products": [],
            "categories": {},
            "error": str(e)
        }


async def analyze_food_text(text: str) -> Dict[str, Any]:
    """
    Анализ текстового описания еды
    """
    # Проверяем наличие API ключа
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        return {
            "description": text,
            "products": [text],
            "categories": {},
            "error": "API key not configured"
        }

    system_prompt = f"""Ты эксперт по питанию. Проанализируй описание еды и верни JSON.

{FOOD_CATEGORIES}

Пользователь описал что съел. Твоя задача:
1. Выделить все продукты из описания
2. Классифицировать их по категориям
3. Сформировать краткое описание

Верни ТОЛЬКО JSON в формате:
{{
    "description": "краткое нормализованное описание",
    "products": ["продукт1", "продукт2"],
    "categories": {{
        "proteins_animal": [],
        "proteins_plant": [],
        "fats": [],
        "carbs_slow": [],
        "carbs_fast": [],
        "vegetables": []
    }}
}}
"""

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": TEXT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    "max_tokens": 400,
                    "temperature": 0.3
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            return json.loads(content)

    except Exception as e:
        return {
            "description": text,
            "products": [text],
            "categories": {},
            "error": str(e)
        }


async def generate_daily_summary(
    food_entries: List[Dict],
    user_goal: str,
    user_gender: str = None,
    user_activity_level: str = None,
    workouts: List[Dict] = None,
    sleep_score: int = None,
    has_training_today: bool = False
) -> Dict[str, Any]:
    """
    Генерация вечернего итога дня с учетом всех факторов

    Args:
        food_entries: список записей о еде
        user_goal: цель пользователя (maintain/lose/gain)
        user_gender: пол пользователя (male/female)
        user_activity_level: ритм дня (active/medium/calm)
        workouts: список тренировок за день
        sleep_score: оценка сна (1-5)
        has_training_today: флаг наличия тренировки (deprecated, используем workouts)
    """
    nutrition_model = NUTRITION_MODELS.get(user_goal, NUTRITION_MODELS["maintain"])

    # Определяем наличие тренировки и общую нагрузку
    has_workouts = bool(workouts and len(workouts) > 0)
    total_workout_minutes = sum(w.get('duration_minutes', 0) for w in (workouts or []))
    avg_intensity = sum(w.get('intensity', 3) for w in (workouts or [])) / len(workouts) if workouts else 0

    # Собираем информацию о тренировках
    workout_summary = ""
    if has_workouts:
        workout_lines = []
        for w in workouts:
            intensity_desc = ["легкая", "легкая+", "средняя", "интенсивная", "очень интенсивная"][w.get('intensity', 3) - 1]
            workout_lines.append(f"- {w.get('workout_name', 'тренировка')}: {w.get('duration_minutes', 0)} мин, {intensity_desc}")
        workout_summary = "\n".join(workout_lines)

    # Информация об осознанном питании
    mindful_eating_count = sum(1 for e in food_entries if e.get('ate_without_gadgets'))
    mindful_eating_note = f"Приемов пищи без гаджетов: {mindful_eating_count} из {len(food_entries)}" if mindful_eating_count > 0 else ""

    # Анализ времени приемов пищи
    meal_times = []
    for entry in food_entries:
        if entry.get('entry_time'):
            meal_times.append(entry['entry_time'])
    meal_times.sort()

    first_meal = meal_times[0] if meal_times else None
    last_meal = meal_times[-1] if meal_times else None
    eating_window = ""
    late_eating_note = ""

    if first_meal and last_meal:
        try:
            first_h = int(first_meal.split(':')[0])
            last_h = int(last_meal.split(':')[0])
            window_hours = last_h - first_h
            eating_window = f"Окно питания: {first_meal} - {last_meal} ({window_hours} ч)"

            if last_h >= 22:
                late_eating_note = "Последний прием пищи был поздно (после 22:00)"
            elif last_h >= 21:
                late_eating_note = "Последний прием пищи был довольно поздно (после 21:00)"
        except:
            pass

    # Собираем все продукты и категории
    all_products = []
    all_categories = {
        "proteins_animal": [],
        "proteins_plant": [],
        "fats": [],
        "carbs_slow": [],
        "carbs_fast": [],
        "vegetables": []
    }

    # Анализ голода и сытости
    hunger_levels = []
    fullness_levels = []

    for entry in food_entries:
        if entry.get('description'):
            all_products.append(entry['description'])
        if entry.get('categories'):
            cats = entry['categories']
            if isinstance(cats, str):
                cats = json.loads(cats)
            for key in all_categories:
                if key in cats:
                    all_categories[key].extend(cats[key])
        if entry.get('hunger_before'):
            hunger_levels.append(entry['hunger_before'])
        if entry.get('fullness_after'):
            fullness_levels.append(entry['fullness_after'])

    # Убираем дубликаты
    for key in all_categories:
        all_categories[key] = list(set(all_categories[key]))

    # Контекст пользователя
    gender_context = ""
    if user_gender == 'male':
        gender_context = "мужчина"
    elif user_gender == 'female':
        gender_context = "женщина"

    activity_context = ""
    if user_activity_level == 'active':
        activity_context = "активный образ жизни (много движения)"
    elif user_activity_level == 'medium':
        activity_context = "умеренная активность"
    elif user_activity_level == 'calm':
        activity_context = "преимущественно сидячий образ жизни"

    goal_context = {
        'maintain': 'поддержание формы',
        'lose': 'снижение веса',
        'gain': 'набор массы'
    }.get(user_goal, 'поддержание формы')

    # Формируем профиль пользователя
    user_profile = f"Профиль: {gender_context}, {activity_context}, цель — {goal_context}."

    # Контекст сна
    sleep_context = ""
    if sleep_score:
        if sleep_score <= 2:
            sleep_context = f"Сон сегодня был плохим ({sleep_score}/5) — это могло повлиять на выбор еды и чувство голода."
        elif sleep_score == 3:
            sleep_context = f"Сон был средним ({sleep_score}/5)."
        else:
            sleep_context = f"Сон был хорошим ({sleep_score}/5)."

    # Контекст голода/сытости
    hunger_fullness_context = ""
    if hunger_levels and fullness_levels:
        avg_hunger = sum(hunger_levels) / len(hunger_levels)
        avg_fullness = sum(fullness_levels) / len(fullness_levels)
        if avg_hunger >= 4:
            hunger_fullness_context = "В среднем садился за еду очень голодным."
        if avg_fullness >= 4.5:
            hunger_fullness_context += " Чаще переедал (высокая сытость после еды)."
        elif avg_fullness <= 2.5:
            hunger_fullness_context += " Возможно, порции были недостаточными."

    system_prompt = f"""Ты дружелюбный помощник по питанию. Твоя задача — дать персонализированный качественный анализ рациона за день.

{user_profile}

ВАЖНЫЕ ПРАВИЛА:
1. НИКОГДА не упоминай калории, граммы, проценты БЖУ
2. Используй ТОЛЬКО качественные формулировки
3. Не осуждай и не ругай
4. Учитывай ВСЕ факторы: пол, активность, цель, тренировки, сон, время приемов пищи
5. Тон: тёплый, поддерживающий, но не приторный
6. Если был плохой сон — учти, что это влияет на тягу к сладкому и быстрым углеводам
7. Если были интенсивные тренировки — потребность в белке и углеводах выше

Ориентир структуры рациона: {nutrition_model['note']}

Примеры ХОРОШИХ формулировок:
- "для дня с интенсивной тренировкой белка могло быть чуть больше"
- "учитывая твою цель снижения веса, рацион выглядит сбалансированным"
- "поздний ужин может влиять на качество сна — попробуй поужинать раньше"
- "при активном образе жизни овощей и клетчатки стоит добавить"
- "после плохого сна тяга к сладкому — это нормально, не вини себя"

Примеры ПЛОХИХ формулировок (НЕ ИСПОЛЬЗОВАТЬ):
- "ты съел 2000 ккал"
- "белка было 30%"
- "это много/мало калорий"
- "ты переел/недоел"

Верни JSON:
{{
    "foods_list": ["список съеденного в читаемом виде"],
    "analysis": "2-4 предложения персонализированного анализа с учетом всех факторов",
    "balance_note": "одно предложение о балансе рациона относительно цели",
    "timing_note": "наблюдение о режиме питания (опционально, null если нечего сказать)",
    "suggestion": "одно мягкое персонализированное предложение на завтра (опционально, может быть null)"
}}
"""

    # Формируем детальное сообщение
    context_parts = []

    if has_workouts:
        context_parts.append(f"Тренировки сегодня:\n{workout_summary}\nОбщее время: {total_workout_minutes} мин, средняя интенсивность: {avg_intensity:.1f}/5")

    if sleep_context:
        context_parts.append(sleep_context)

    if eating_window:
        context_parts.append(eating_window)

    if late_eating_note:
        context_parts.append(late_eating_note)

    if mindful_eating_note:
        context_parts.append(mindful_eating_note)

    if hunger_fullness_context:
        context_parts.append(hunger_fullness_context)

    context_block = "\n".join(context_parts) if context_parts else "Дополнительного контекста нет."

    user_message = f"""
Сегодня пользователь съел:
{json.dumps(all_products, ensure_ascii=False)}

Времена приемов пищи: {', '.join(meal_times) if meal_times else 'не указаны'}

Категории продуктов:
{json.dumps(all_categories, ensure_ascii=False)}

Контекст дня:
{context_block}
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": TEXT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "max_tokens": 600,
                    "temperature": 0.7
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            return json.loads(content)

    except Exception as e:
        return {
            "foods_list": all_products,
            "analysis": "Не удалось сгенерировать анализ",
            "balance_note": "",
            "suggestion": None,
            "error": str(e)
        }


async def generate_weekly_summary(
    food_by_day: Dict[str, List[Dict]],
    sleep_by_day: Dict[str, Optional[int]],
    workouts_by_day: Dict[str, List[Dict]],
    user_goal: str,
    user_gender: str = None,
    user_activity_level: str = None
) -> Dict[str, Any]:
    """
    Генерация умного недельного обзора с глубоким анализом паттернов и связей

    Args:
        food_by_day: еда по дням
        sleep_by_day: оценки сна по дням
        workouts_by_day: тренировки по дням
        user_goal: цель пользователя
        user_gender: пол пользователя
        user_activity_level: ритм дня
    """
    DAY_NAMES = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']

    # Подготавливаем данные для глубокого анализа
    daily_data = []
    for date in sorted(food_by_day.keys()):
        food_entries = food_by_day[date]
        sleep_score = sleep_by_day.get(date)
        day_workouts = workouts_by_day.get(date, [])

        # Получаем день недели
        try:
            from datetime import datetime as dt
            date_obj = dt.strptime(date, '%Y-%m-%d')
            day_name = DAY_NAMES[date_obj.weekday()]
        except:
            day_name = date

        products = []
        categories_count = {
            "proteins": 0,
            "fats": 0,
            "carbs_slow": 0,
            "carbs_fast": 0,
            "vegetables": 0
        }

        # Анализ времени приемов пищи
        meal_times = []
        hunger_levels = []
        fullness_levels = []
        mindful_meals = 0

        for entry in food_entries:
            if entry.get('description'):
                products.append(entry['description'])
            if entry.get('entry_time'):
                meal_times.append(entry['entry_time'])
            if entry.get('hunger_before'):
                hunger_levels.append(entry['hunger_before'])
            if entry.get('fullness_after'):
                fullness_levels.append(entry['fullness_after'])
            if entry.get('ate_without_gadgets'):
                mindful_meals += 1

            if entry.get('categories'):
                cats = entry['categories']
                if isinstance(cats, str):
                    cats = json.loads(cats)
                if cats.get('proteins_animal'):
                    categories_count['proteins'] += len(cats['proteins_animal'])
                if cats.get('proteins_plant'):
                    categories_count['proteins'] += len(cats['proteins_plant'])
                if cats.get('fats'):
                    categories_count['fats'] += len(cats['fats'])
                if cats.get('carbs_slow'):
                    categories_count['carbs_slow'] += len(cats['carbs_slow'])
                if cats.get('carbs_fast'):
                    categories_count['carbs_fast'] += len(cats['carbs_fast'])
                if cats.get('vegetables'):
                    categories_count['vegetables'] += len(cats['vegetables'])

        # Вычисляем время последнего приема пищи
        last_meal_hour = None
        if meal_times:
            meal_times.sort()
            try:
                last_meal_hour = int(meal_times[-1].split(':')[0])
            except:
                pass

        # Информация о тренировках
        workout_info = None
        if day_workouts:
            total_mins = sum(w.get('duration_minutes', 0) for w in day_workouts)
            avg_intensity = sum(w.get('intensity', 3) for w in day_workouts) / len(day_workouts)
            workout_info = {
                "count": len(day_workouts),
                "total_minutes": total_mins,
                "avg_intensity": round(avg_intensity, 1)
            }

        daily_data.append({
            "date": date,
            "day": day_name,
            "meals_count": len(food_entries),
            "products_count": len(products),
            "categories": categories_count,
            "sleep": sleep_score,
            "last_meal_hour": last_meal_hour,
            "avg_hunger": round(sum(hunger_levels) / len(hunger_levels), 1) if hunger_levels else None,
            "avg_fullness": round(sum(fullness_levels) / len(fullness_levels), 1) if fullness_levels else None,
            "mindful_meals": mindful_meals,
            "workout": workout_info
        })

    # Формируем профиль пользователя
    gender_text = {"male": "мужчина", "female": "женщина"}.get(user_gender, "")
    activity_text = {
        "active": "активный образ жизни",
        "medium": "умеренная активность",
        "calm": "сидячий образ жизни"
    }.get(user_activity_level, "")
    goal_text = {
        "maintain": "поддержание формы",
        "lose": "снижение веса",
        "gain": "набор массы"
    }.get(user_goal, "поддержание")

    user_profile = f"Профиль: {gender_text}, {activity_text}, цель — {goal_text}." if gender_text else f"Цель: {goal_text}."

    system_prompt = f"""Ты аналитик привычек питания и здоровья. Твоя задача — найти ГЛУБОКИЕ ПАТТЕРНЫ и СВЯЗИ в данных за неделю.

{user_profile}

ВАЖНЫЕ ПРАВИЛА:
1. НЕ используй калории и проценты
2. Ищи СВЯЗИ между факторами: сон ↔ питание, тренировки ↔ аппетит, время ужина ↔ качество сна
3. Отмечай ПАТТЕРНЫ по дням недели (например: "по понедельникам питание беднее")
4. Анализируй КОМПЛЕКСНОСТЬ питания — наличие всех групп продуктов
5. Тон: нейтральный, наблюдательный, без осуждения
6. Будь конкретным — ссылайся на конкретные дни

ТИПЫ СВЯЗЕЙ, которые нужно искать:
- Плохой сон → больше быстрых углеводов/сладкого на следующий день
- Поздний ужин (после 21-22) → плохой сон этой ночью
- Интенсивная тренировка → повышенный аппетит
- Высокий голод перед едой → переедание (высокая сытость)
- Дни без овощей → менее сбалансированное питание
- Осознанное питание (без гаджетов) → лучшее насыщение

Примеры ХОРОШИХ наблюдений:
- "В среду после плохого сна (2/5) было больше сладкого — это нормальная реакция организма"
- "Поздние ужины во вторник и четверг совпали с худшими оценками сна на следующий день"
- "В дни с тренировками белок присутствовал стабильно — отлично для восстановления"
- "По выходным питание разнообразнее — возможно, больше времени на готовку"
- "Когда ел без гаджетов, сытость была выше при тех же порциях"

Верни JSON:
{{
    "week_overview": "2-3 предложения общей картины недели",
    "food_diversity_by_day": {{"пн": "высокое|среднее|низкое", ...}},
    "sleep_food_patterns": ["связь 1 между сном и питанием", "связь 2"],
    "workout_patterns": ["наблюдение о связи тренировок и питания"] или null,
    "timing_patterns": ["наблюдения о времени питания и его влиянии"],
    "balance_insights": ["инсайт о комплексности рациона по дням"],
    "mindful_eating_note": "наблюдение об осознанном питании или null",
    "key_pattern": "ГЛАВНЫЙ паттерн недели — одно самое важное наблюдение",
    "sleep_average": 3.5
}}
"""

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": TEXT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Данные за неделю:\n{json.dumps(daily_data, ensure_ascii=False, indent=2)}"}
                    ],
                    "max_tokens": 1200,
                    "temperature": 0.7
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            result = json.loads(content)

            # Вычисляем средний сон, если не вернулся
            if not result.get('sleep_average'):
                sleep_scores = [s for s in sleep_by_day.values() if s]
                result['sleep_average'] = round(sum(sleep_scores) / len(sleep_scores), 1) if sleep_scores else None

            return result

    except Exception as e:
        return {
            "week_overview": "Не удалось сгенерировать обзор",
            "food_diversity_by_day": {},
            "sleep_food_patterns": [],
            "workout_patterns": None,
            "timing_patterns": [],
            "balance_insights": [],
            "mindful_eating_note": None,
            "key_pattern": None,
            "sleep_average": None,
            "error": str(e)
        }
