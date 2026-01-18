import asyncio, json, os, sys
from telethon import TelegramClient
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import UsernameNotOccupiedError
from telethon.tl.types import InputPeerChannel

API_ID   = int(os.getenv("TG_API_ID", "123456"))      # <<< ВСТАВЬ
API_HASH = os.getenv("TG_API_HASH", "abcdef123456")    # <<< ВСТАВЬ
SESSION  = os.getenv("TG_SESSION", "audit_session")
CHAT_ID  = int(os.getenv("GROUP_ID", "0"))             # берём из .env группы бота

async def resolve_chat(client, chat_id: int):
    # У нас есть numeric ID канала/супергруппы вида -100...
    # Превратим его в entity
    entity = await client.get_entity(chat_id)
    return entity

async def main():
    if CHAT_ID == 0:
        print("GROUP_ID не найден. Проверь .env")
        sys.exit(1)
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()  # авторизация по телефону произойдёт автоматически

    entity = await resolve_chat(client, CHAT_ID)
    members = []
    async for u in client.iter_participants(entity, aggressive=True):
        members.append({
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "bot": bool(u.bot),
            "is_self": getattr(u, "is_self", False)
        })
    out = "tools/members.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(members, f, ensure_ascii=False, indent=2)
    print(f"Сохранено участников: {len(members)} -> {out}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
