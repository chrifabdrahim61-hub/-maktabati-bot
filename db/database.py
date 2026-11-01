"""SQLite (async via aiosqlite) — one shared connection lives in app.bot_data['db']."""
import aiosqlite

from config import DATA_DIR

DB_PATH = DATA_DIR / "bookbot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    first_name TEXT,
    username   TEXT,
    lang       TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    last_seen  TEXT
);
"""


async def init_db(app) -> None:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(_SCHEMA)
    await conn.commit()
    app.bot_data["db"] = conn


async def close_db(app) -> None:
    conn = app.bot_data.get("db")
    if conn is not None:
        await conn.close()
