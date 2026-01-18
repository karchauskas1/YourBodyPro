import os, sqlite3, time
from datetime import datetime, timezone
from collections import defaultdict

from dotenv import load_dotenv
from yookassa import Configuration, Payment

# === Конфиг из .env ===
load_dotenv()
SHOP_ID = os.getenv("SHOP_ID")
SHOP_SECRET_KEY = os.getenv("SHOP_SECRET_KEY")
DB_PATH = os.getenv("DB_PATH") or "bot.db"
PAID_DAYS = int(os.getenv("PAID_DAYS") or 30)
GRACE_DAYS = int(os.getenv("GRACE_DAYS") or 1)

if not SHOP_ID or not SHOP_SECRET_KEY:
    raise SystemExit("SHOP_ID / SHOP_SECRET_KEY не заданы в .env")

Configuration.account_id = SHOP_ID
Configuration.secret_key = SHOP_SECRET_KEY

paid_sec  = PAID_DAYS * 86400
grace_sec = GRACE_DAYS * 86400

def to_ts(iso_str: str) -> int:
    s = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return int(dt.astimezone(timezone.utc).timestamp())

def fetch_all_succeeded():
    """
    Возвращает список платежей со статусом succeeded.
    Каждый элемент: (user_id:int, created_ts:int)
    """
    out = []
    params = {"limit": 100}
    while True:
        page = Payment.list(params)
        items = getattr(page, "items", []) or []
        for p in items:
            try:
                if getattr(p, "status", "") != "succeeded":
                    continue
                md = getattr(p, "metadata", {}) or {}
                uid_raw = md.get("user_id")
                if uid_raw is None:
                    continue
                uid = int(str(uid_raw))
                created_iso = str(p.created_at)
                ts = to_ts(created_iso)
                out.append((uid, ts))
            except Exception:
                continue
        cursor = getattr(page, "next_cursor", None)
        if not cursor:
            break
        params = {"limit": 100, "cursor": cursor}
    return out

def recompute_expiry(payments):
    """
    payments: list[(uid, ts)]
    Логика: для каждого uid сортируем оплаты, накатываем месяцы подряд;
    если была пауза — стартуем от времени оплаты; грейс добавляем один раз в конце.
    """
    per_user = defaultdict(list)
    for uid, ts in payments:
        per_user[uid].append(ts)
    res = {}
    for uid, ts_list in per_user.items():
        ts_list.sort()
        exp = 0
        for ts in ts_list:
            if exp < ts:
                exp = ts
            exp += paid_sec
        exp += grace_sec
        res[uid] = exp
    return res

def main():
    print("→ Тяну успешные платежи из ЮKassa…")
    pays = fetch_all_succeeded()
    print(f"→ Получено платежей: {len(pays)}")

    mapping = recompute_expiry(pays)
    print(f"→ Пользователей с платежами: {len(mapping)}")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        username   TEXT,
        full_name  TEXT,
        expires_at INTEGER DEFAULT 0
    )
    """)

    updated = 0
    inserted = 0
    for uid, new_exp in mapping.items():
        row = cur.execute("SELECT expires_at FROM users WHERE user_id=?", (uid,)).fetchone()
        if row:
            old_exp = row[0] or 0
            eff = max(old_exp, new_exp)
            cur.execute("UPDATE users SET expires_at=? WHERE user_id=?", (eff, uid))
            updated += 1
        else:
            cur.execute("INSERT INTO users(user_id, expires_at) VALUES(?,?)", (uid, new_exp))
            inserted += 1

    con.commit()
    con.close()

    print(f"✓ Готово. Обновлено: {updated}, добавлено: {inserted}")
    print("Топ 10 ближайших окончаний (локальное время сервера):")
    os.system(f'''sqlite3 "{DB_PATH}" "SELECT user_id, datetime(expires_at,'unixepoch','localtime') FROM users WHERE expires_at>0 ORDER BY expires_at ASC LIMIT 10;"''')

if __name__ == "__main__":
    main()
