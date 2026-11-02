"""SQLite (async via aiosqlite) — one shared connection lives in app.bot_data['db']."""
import aiosqlite

from config import DATA_DIR

DB_PATH = DATA_DIR / "bookbot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    first_name  TEXT,
    username    TEXT,
    lang        TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    last_seen   TEXT,
    credits     INTEGER NOT NULL DEFAULT 5,
    last_refill INTEGER NOT NULL DEFAULT 0,
    referred_by INTEGER
);
"""

# Step 6e: databases created before the credits system only have the first
# six columns — these ALTERs add the rest. Idempotent (duplicate-column
# errors are expected and swallowed). Existing users wake up with the
# welcome credits and a fresh 24 h refill clock.
_MIGRATIONS = (
    "ALTER TABLE users ADD COLUMN credits INTEGER NOT NULL DEFAULT 5",
    "ALTER TABLE users ADD COLUMN last_refill INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN referred_by INTEGER",
)


async def apply_migrations(conn: aiosqlite.Connection) -> None:
    for sql in _MIGRATIONS:
        try:
            await conn.execute(sql)
        except aiosqlite.OperationalError:
            pass  # column already exists (fresh schema) — fine
    await conn.execute(
        "UPDATE users SET last_refill = CAST(strftime('%s','now') AS INTEGER) "
        "WHERE last_refill = 0"
    )
    await conn.commit()


async def init_db(app) -> None:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(_SCHEMA)
    await apply_migrations(conn)
    app.bot_data["db"] = conn


async def close_db(app) -> None:
    conn = app.bot_data.get("db")
    if conn is not None:
        await conn.close()
