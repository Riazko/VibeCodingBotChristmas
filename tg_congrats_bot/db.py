import aiosqlite
from datetime import datetime

DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            registered_at TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        await db.commit()


async def upsert_user(user):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO users (user_id, username, first_name, registered_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username
        """, (
            user.id,
            user.username,
            user.first_name,
            datetime.utcnow().isoformat()
        ))
        await db.commit()


async def get_user_id_by_username(username: str) -> int | None:
    username = username.lstrip("@").lower()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE LOWER(username)=? LIMIT 1",
            (username,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def save_message(sender_id: int, recipient_id: int, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO messages (sender_id, recipient_id, text, created_at)
        VALUES (?, ?, ?, ?)
        """, (
            sender_id,
            recipient_id,
            text,
            datetime.utcnow().isoformat()
        ))
        await db.commit()
