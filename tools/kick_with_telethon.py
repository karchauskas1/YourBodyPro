import asyncio
import sqlite3
import os
from datetime import datetime
from telethon import TelegramClient

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
group_id = int(os.getenv("GROUP_ID"))
db_path = "bot.db"

async def main():
    client = TelegramClient("session", api_id, api_hash)
    await client.start()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT user_id, expires_at FROM users")
    users = cur.fetchall()

    now = datetime.now().timestamp()
    expired_users = [u for u in users if u[1] and u[1] < now]

    print(f"Просроченных подписок: {len(expired_users)}")

    async for member in client.iter_participants(group_id):
        for user_id, expires_at in expired_users:
            if member.id == user_id:
                try:
                    await client.kick_participant(group_id, user_id)
                    print(f"❌ Кикнут: {user_id}")
                except Exception as e:
                    print(f"Ошибка кика {user_id}: {e}")

    await client.disconnect()
    conn.close()

asyncio.run(main())
