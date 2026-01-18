import os, sqlite3, time
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import RPCError

load_dotenv(os.path.join('/opt/tg-bot', '.env'))

API_ID   = int(os.getenv('TG_API_ID', '0'))      # <- подставь ниже через export
API_HASH = os.getenv('TG_API_HASH', '')          # <- подставь ниже через export
GROUP_ID = int(os.getenv('GROUP_ID', '0'))       # -100...
DB_PATH  = os.getenv('DB_PATH', 'bot.db')

assert API_ID and API_HASH and GROUP_ID, "API_ID/API_HASH/GROUP_ID должны быть заданы"

now = int(time.time())
# читаем все expires из БД
con = sqlite3.connect(DB_PATH)
cur = con.execute("SELECT user_id, COALESCE(expires_at,0) FROM users")
expires = {row[0]: row[1] for row in cur.fetchall()}
con.close()

client = TelegramClient('audit_session', API_ID, API_HASH)
client.start()  # при первом запуске спросит код подтверждения

expired_in_db = {uid for uid, exp in expires.items() if exp == 0 or exp <= now}

print(f"[i] В БД истёкших: {len(expired_in_db)}. Проверяю, кто реально в чате…")

still_in_chat = []
async def main():
    global still_in_chat
    try:
        async for p in client.iter_participants(GROUP_ID):
            if p.bot:
                continue
            if p.id in expired_in_db:
                still_in_chat.append((p.id, p.username or "", p.first_name or "", p.last_name or ""))
    except RPCError as e:
        print("[!] Telethon error:", e)

with client:
    client.loop.run_until_complete(main())

print(f"[✓] В чате найдено истёкших: {len(still_in_chat)}")
if still_in_chat:
    print("user_id, username, first_name, last_name")
    for uid, uname, fn, ln in still_in_chat:
        print(f"{uid}, @{uname}, {fn}, {ln}")
