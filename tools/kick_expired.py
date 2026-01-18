import os
import asyncio
import aiosqlite
from datetime import datetime, timezone
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

# Берём из .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID  = int(os.getenv("GROUP_ID", "0"))

# Порог "просрочено" — текущее UTC-время в секундах
def now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())

async def kick(bot: Bot, uid: int) -> bool:
    """
    Пытаемся удалить пользователя из группы.
    True  — кик сработал или его уже нет в чате,
    False — кикнуть не удалось (нет прав/пользователь админ/владелец и т.п.)
    """
    try:
        member = await bot.get_chat_member(GROUP_ID, uid)
        status = getattr(member, "status", None)
        if status in ("left", "kicked"):
            return True  # уже не в чате — считаем успех
        if status in ("administrator", "creator"):
            return False  # админ/владелец — не трогаем
        # мягкий кик: бан на минуту и тут же анбан, чтобы удалить
        await bot.ban_chat_member(GROUP_ID, uid, until_date=now_ts() + 60)
        await bot.unban_chat_member(GROUP_ID, uid)
        return True
    except TelegramBadRequest as e:
        # Частые кейсы: "USER_NOT_PARTICIPANT", "can't remove chat owner" и т.п.
        text = str(e)
        if "USER_NOT_PARTICIPANT" in text:
            return True
        return False
    except TelegramForbiddenError:
        # Нет прав кикать
        return False
    except Exception:
        return False

async def main(dry_run: bool = False, limit: int | None = None, verbose: bool = False):
    if not BOT_TOKEN or not GROUP_ID:
        raise SystemExit("Нет BOT_TOKEN или GROUP_ID в окружении (.env).")

    bot = Bot(BOT_TOKEN)
    n_now = now_ts()

    async with aiosqlite.connect("bot.db") as db:
        q = "SELECT user_id FROM users WHERE expires_at>0 AND expires_at < ?"
        params = [n_now]
        if limit:
            q += " ORDER BY expires_at LIMIT ?"
            params.append(limit)
        cur = await db.execute(q, params)
        rows = await cur.fetchall()

    expired = [r[0] for r in rows]
    print(f"Найдено просроченных: {len(expired)}")

    kicked = 0
    skipped = 0
    for uid in expired:
        if dry_run:
            if verbose: print(f"[DRY] Проверка {uid}")
            continue
        ok = await kick(bot, uid)
        if ok:
            kicked += 1
            if verbose: print(f"OK  кикнут/нет в чате: {uid}")
        else:
            skipped += 1
            if verbose: print(f"SKIP админ/нет прав/ошибка: {uid}")

    print(f"Готово. Кикнуты: {kicked}, пропущены: {skipped}, всего просроченных: {len(expired)}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Только показать, без кика")
    p.add_argument("--limit", type=int, default=None, help="Ограничить кол-во записей")
    p.add_argument("--verbose", action="store_true", help="Подробный вывод")
    args = p.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit, verbose=args.verbose))
