# tools/audit_and_kick.py
# Обходит ВСЕХ участников группы и кикает всех, кто НЕ активен по базе.
# Активен = есть в таблице users и expires_at > now().
# Все остальные (нет записи, NULL/0, просрочено) — кик.

import os
import asyncio
import sqlite3
import time

from telethon import TelegramClient, errors

# --- окружение ---
API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
GROUP_ID = int(os.environ["GROUP_ID"])          # пример: -1002862714592
DB_PATH = os.environ.get("DB_PATH", "bot.db")   # пример: /opt/tg-bot/bot.db
SESSION_FILE = "tools/audit.session"            # сохраняем логин тут

def now_ts() -> int:
    return int(time.time())

def load_active_user_ids(db_path: str) -> set[int]:
    """
    Возвращает set user_id, у кого expires_at в будущем (строго активные).
    Все остальные считаются НЕ активными.
    """
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute("SELECT user_id FROM users WHERE expires_at > ?", (now_ts(),))
        return {int(r[0]) for r in cur.fetchall()}
    finally:
        con.close()

async def kick_soft(client: TelegramClient, uid: int) -> bool:
    """
    Мягкий кик: бан (view_messages=False) + мгновенный разбан (view_messages=True),
    чтобы можно было вернуться по новой инвайт-ссылке.
    """
    try:
        # ban
        await client.edit_permissions(GROUP_ID, uid, view_messages=False)
        await asyncio.sleep(0.2)
        # unban (разбан)
        await client.edit_permissions(GROUP_ID, uid, view_messages=True)
        return True
    except (errors.UserAdminInvalidError, errors.ChatAdminRequiredError):
        return False
    except Exception as e:
        print(f"[ERR] kick {uid}: {e}")
        return False

async def main():
    active = load_active_user_ids(DB_PATH)
    print(f"[i] Активных по базе: {len(active)}")

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()  # при первом запуске спросит код и пароль — далее не спрашивает
    me = await client.get_me()
    print(f"[i] Зашли как: {me.first_name} (@{getattr(me, 'username', '')})")

    kicked = 0
    skipped_admin = 0
    skipped_error = 0

    # Идём по всем участникам. Никаких offset/limit — Telethon сам пагинирует.
    async for user in client.iter_participants(GROUP_ID):
        uid = int(user.id)

        # Пробуем кикнуть только НЕ активных:
        if uid in active:
            continue

        # Пробуем бан/разбан, а если это админ — поймаем исключение и пропустим
        ok = await kick_soft(client, uid)
        if ok:
            kicked += 1
            print(f"[KICK] {uid} @{getattr(user, 'username', '')}")
        else:
            # либо админ, либо нет прав кикать, либо другая ошибка
            skipped_error += 1
            print(f"[SKIP] не удалось кикнуть: {uid} @{getattr(user, 'username', '')}")

        # Чуть-чуть замедлимся, чтобы не ловить FLOOD_WAIT
        await asyncio.sleep(0.4)

    print(f"[done] Кикнуто: {kicked}, пропущено(ошибки/админы): {skipped_error}, админов (по ошибкам): {skipped_admin}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
