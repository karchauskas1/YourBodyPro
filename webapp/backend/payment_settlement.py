"""Apply a provider-confirmed payment once, across both bot and API processes."""
import time
import uuid

import aiosqlite


def renewal_idempotency_key(user_id: int, expires_at: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'yourbody-renewal:{user_id}:{expires_at}'))


async def settle_payment(db_path: str, user_id: int, payment_id: str, paid_days: int, grace_days: int):
    # A separate connection keeps the transaction independent of unrelated tracker writes.
    async with aiosqlite.connect(db_path, timeout=10) as connection:
        await connection.execute('BEGIN IMMEDIATE')
        try:
            cursor = await connection.execute('SELECT user_id, status FROM payments WHERE payment_id = ?', (payment_id,))
            payments = await cursor.fetchall()
            if not payments or any(row[0] != user_id for row in payments):
                raise ValueError('Payment does not belong to this user')
            cursor = await connection.execute('SELECT expires_at FROM users WHERE user_id = ?', (user_id,))
            user = await cursor.fetchone()
            if not user:
                raise ValueError('Payment user does not exist')
            now = int(time.time())
            existing = user[0] or 0
            was_active = existing > now
            applied = not any(row[1] == 'succeeded' for row in payments)
            expires_at = existing
            if applied:
                # Retain remaining access and apply the project's configured paid/grace period.
                expires_at = max(now, existing) + (paid_days + grace_days) * 86400
                await connection.execute(
                    'UPDATE users SET expires_at=?, remind_3_sent=0, remind_2_sent=0, remind_1_sent=0 WHERE user_id=?',
                    (expires_at, user_id),
                )
                await connection.execute("UPDATE payments SET status='succeeded' WHERE payment_id=? AND user_id=?", (payment_id, user_id))
            await connection.commit()
            return {'applied': applied, 'expires_at': expires_at, 'was_active': was_active}
        except BaseException:
            await connection.rollback()
            raise
