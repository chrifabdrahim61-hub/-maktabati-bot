"""Data-access helpers for the SQLite database (users, credits, referrals)."""
import config
from db.database import DB_PATH  # noqa: F401  (re-export for convenience)


async def upsert_user(
    db, user_id: int, first_name: str | None, username: str | None,
    referred_by: int | None = None,
) -> bool:
    """Insert the user or refresh profile info — never touches their chosen
    lang, credits or referral state.

    `referred_by` is only stored on the very first insert (a genuine
    invitation); later /start calls can't re-attribute the user.
    Returns True only when the row was just created (their first contact).
    """
    cur = await db.execute(
        """
        INSERT INTO users (user_id, first_name, username, last_seen,
                           credits, last_refill, referred_by)
        VALUES (?, ?, ?, datetime('now'), ?,
                CAST(strftime('%s','now') AS INTEGER), ?)
        ON CONFLICT(user_id) DO NOTHING
        """,
        (user_id, first_name, username, config.WELCOME_CREDITS, referred_by),
    )
    created = cur.rowcount == 1
    await db.execute(
        "UPDATE users SET first_name = ?, username = ?, last_seen = datetime('now') "
        "WHERE user_id = ?",
        (first_name, username, user_id),
    )
    await db.commit()
    return created


async def enroll(db, user_id: int) -> None:
    """Row for a user who texted without ever /start-ing — welcome credits,
    no profile overwrite (INSERT-only, safe to call any time)."""
    await db.execute(
        """
        INSERT INTO users (user_id, credits, last_refill)
        VALUES (?, ?, CAST(strftime('%s','now') AS INTEGER))
        ON CONFLICT(user_id) DO NOTHING
        """,
        (user_id, config.WELCOME_CREDITS),
    )
    await db.commit()


async def get_lang(db, user_id: int) -> str | None:
    async with db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    return row["lang"] if row else None


async def set_lang(db, user_id: int, lang: str) -> None:
    await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    await db.commit()


async def get_credit_row(db, user_id: int):
    """(credits, last_refill) row or None — used by the credits gate."""
    async with db.execute(
        "SELECT credits, last_refill FROM users WHERE user_id = ?", (user_id,)
    ) as cur:
        return await cur.fetchone()


async def add_credits(db, user_id: int, delta: int) -> int:
    """Apply delta (clamped at 0 — credits can't go negative), return balance."""
    cur = await db.execute(
        "UPDATE users SET credits = MAX(0, credits + ?) WHERE user_id = ?",
        (delta, user_id),
    )
    if cur.rowcount == 0:  # user texted without /start ever — enroll on the fly
        await enroll(db, user_id)
        cur = await db.execute(
            "UPDATE users SET credits = MAX(0, credits + ?) WHERE user_id = ?",
            (delta, user_id),
        )
    await db.commit()
    row = await get_credit_row(db, user_id)
    return row["credits"] if row else 0


async def refill_if_due(db, user_id: int) -> None:
    """+DAILY_REFILL once every REFILL_PERIOD (rolling 24 h) — one atomic
    UPDATE, so double-calls within the window are harmless."""
    await db.execute(
        """
        UPDATE users
        SET credits = credits + ?,
            last_refill = CAST(strftime('%s','now') AS INTEGER)
        WHERE user_id = ?
          AND last_refill + ? <= CAST(strftime('%s','now') AS INTEGER)
        """,
        (config.DAILY_REFILL, user_id, config.REFILL_PERIOD),
    )
    await db.commit()


async def reward_referral(db, referrer_id: int, invitee_id: int) -> int | None:
    """+REFERRAL_BONUS for an EXISTING user whose link brought a new user in.
    Returns the referrer's new balance, or None when there is no such user
    (never bonus strangers) or when someone tries to invite themselves."""
    if referrer_id == invitee_id:
        return None
    if await get_credit_row(db, referrer_id) is None:
        return None
    return await add_credits(db, referrer_id, config.REFERRAL_BONUS)
