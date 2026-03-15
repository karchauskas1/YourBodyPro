import asyncio
import aiosqlite
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bot.db")

session = AiohttpSession(proxy="socks5://127.0.0.1:1080")
bot = Bot(BOT_TOKEN, session=session)

async def kick_no_subs():
    print("🔍 Проверяем базу...")
    conn = await aiosqlite.connect(DB_PATH)
    cur = await conn.execute("SELECT user_id, username, expires_at FROM users")
    rows = await cur.fetchall()
    await conn.close()

    total = len(rows)
    print(f"📦 Всего пользователей в базе: {total}")

    kicked = 0
    skipped = 0

    for uid, username, expires_at in rows:
        if not expires_at or expires_at == 0:
            try:
                await bot.ban_chat_member(GROUP_ID, uid, until_date=int(datetime.now(timezone.utc).timestamp()) + 60)
                await bot.unban_chat_member(GROUP_ID, uid)
                kicked += 1
                print(f"❌ Кикнут @{username or uid}")
            except Exception as e:
                print(f"⚠️ Не удалось кикнуть @{username or uid}: {e}")
                skipped += 1

    print(f"\n✅ Готово. Кикнуто: {kicked}, пропущено: {skipped}, всего проверено: {total}")

asyncio.run(kick_no_subs())
