"""Data-access helpers for the SQLite database."""
from db.database import DB_PATH  # noqa: F401  (re-export for convenience)


async def upsert_user(db, user_id: int, first_name: str | None, username: str | None) -> None:
    """Insert the user or refresh profile info — never touches their chosen lang."""
    await db.execute(
        """
        INSERT INTO users (user_id, first_name, username, last_seen)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            first_name = excluded.first_name,
            username   = excluded.username,
            last_seen  = excluded.last_seen
        """,
        (user_id, first_name, username),
    )
    await db.commit()


async def get_lang(db, user_id: int) -> str | None:
    async with db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    return row["lang"] if row else None


async def set_lang(db, user_id: int, lang: str) -> None:
    await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    await db.commit()
