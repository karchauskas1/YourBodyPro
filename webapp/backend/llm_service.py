# webapp/backend/llm_service.py
# Интеграция с OpenRouter для анализа еды и генерации итогов

import httpx
import base64
import json
import os
from typing import Optional, Dict, Any, List

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
    has_training_today: bool = False
) -> Dict[str, Any]:
    """
    Генерация вечернего итога дня
    """
    nutrition_model = NUTRITION_MODELS.get(user_goal, NUTRITION_MODELS["maintain"])

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

    # Убираем дубликаты
    for key in all_categories:
        all_categories[key] = list(set(all_categories[key]))

    system_prompt = f"""Ты дружелюбный помощник по питанию. Твоя задача — дать качественный анализ рациона за день.

ВАЖНЫЕ ПРАВИЛА:
1. НИКОГДА не упоминай калории, граммы, проценты БЖУ
2. Используй ТОЛЬКО качественные формулировки
3. Не осуждай и не ругай
4. Будь кратким и полезным
5. Тон: тёплый, поддерживающий, но не приторный

Цель пользователя: {user_goal}
Ориентир структуры рациона: {nutrition_model['note']}
День с тренировкой: {'да' if has_training_today else 'нет'}

Примеры ХОРОШИХ формулировок:
- "в рационе сегодня преобладали быстрые углеводы"
- "белковая часть была представлена слабо"
- "рацион выглядел сбалансированным для дня с тренировкой"
- "овощей было немного — попробуй добавить их завтра"

Примеры ПЛОХИХ формулировок (НЕ ИСПОЛЬЗОВАТЬ):
- "ты съел 2000 ккал"
- "белка было 30%"
- "это много/мало калорий"
- "ты переел/недоел"

Верни JSON:
{{
    "foods_list": ["список съеденного в читаемом виде"],
    "analysis": "2-3 предложения анализа",
    "balance_note": "одно предложение о балансе рациона",
    "suggestion": "одно мягкое предложение на завтра (опционально, может быть null)"
}}
"""

    user_message = f"""
Сегодня пользователь съел:
{json.dumps(all_products, ensure_ascii=False)}

Категории продуктов:
{json.dumps(all_categories, ensure_ascii=False)}
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
    user_goal: str
) -> Dict[str, Any]:
    """
    Генерация недельного обзора
    """
    # Подготавливаем данные для анализа
    daily_data = []
    for date in sorted(food_by_day.keys()):
        food_entries = food_by_day[date]
        sleep_score = sleep_by_day.get(date)

        products = []
        categories_count = {
            "proteins": 0,
            "fats": 0,
            "carbs_slow": 0,
            "carbs_fast": 0,
            "vegetables": 0
        }

        for entry in food_entries:
            if entry.get('description'):
                products.append(entry['description'])
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

        daily_data.append({
            "date": date,
            "products_count": len(products),
            "categories": categories_count,
            "sleep": sleep_score
        })

    system_prompt = f"""Ты помощник по анализу привычек. Проанализируй данные за неделю.

ВАЖНЫЕ ПРАВИЛА:
1. НЕ давай инструкций "что делать"
2. НЕ используй калории и проценты
3. Только ПАТТЕРНЫ и СВЯЗИ
4. Тон нейтральный, без оценок
5. Кратко и по делу

Цель пользователя: {user_goal}

Примеры ХОРОШИХ наблюдений:
- "В дни с оценкой сна ниже 3 рацион был менее разнообразным"
- "По четвергам питание однообразнее — возможно, это загруженный день"
- "Овощи появлялись в рационе 4 из 7 дней"
- "Белковые продукты присутствовали стабильно"

Верни JSON:
{{
    "food_diversity_by_day": {{"пн": "высокое|среднее|низкое", ...}},
    "sleep_average": 3.5,
    "patterns": ["паттерн 1", "паттерн 2"],
    "food_sleep_connection": "наблюдение о связи сна и питания или null"
}}
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
                        {"role": "user", "content": json.dumps(daily_data, ensure_ascii=False)}
                    ],
                    "max_tokens": 700,
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
            "food_diversity_by_day": {},
            "sleep_average": None,
            "patterns": [],
            "food_sleep_connection": None,
            "error": str(e)
        }
