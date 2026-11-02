"""Step 6e: credits + referral economy (user request).

«setting credits to every user except me "8974969463" is to give every user
5 free credits and 2 credits every day and he can top up his credits by
sending their referral link to another persons and get for every invitation
1 credit and if he runs out of credits the bot doesnt work until he send
the referral link or wait 24h»

Economy (all tunables live in config.py):
  • new user      → WELCOME_CREDITS (5)
  • every 24 h    → +DAILY_REFILL (2), lazily applied at their next message
  • per invitation→ +REFERRAL_BONUS (1) when someone first-starts the bot
                    via the personal link  t.me/<bot>?start=ref<user_id>
  • search        → 1 credit per SUCCESSFUL search (a miss costs nothing —
                    friendlier, and NL/translation retries look like misses)
  • at 0 credits  → the bot stops searching; the user gets their personal
                    invite link (+ a Telegram share button) or waits for the
                    next +2 refill — exactly the requested behaviour
  • OWNER_ID      → exempt from credits and from the channel gate
"""
import logging
import math
import time
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes

import config
from db import repo
from i18n.detect import from_telegram_locale
from i18n.i18n import t

logger = logging.getLogger(__name__)


def is_owner(user_id: int) -> bool:
    return user_id == config.OWNER_ID


def ref_link(bot_username: str, user_id: int) -> str:
    """The user's personal invite link — one credit per friend who starts."""
    return f"https://t.me/{bot_username}?start=ref{user_id}"


def parse_ref(args: list[str] | None) -> int | None:
    """/start ref123456 → 123456; anything else → None."""
    if not args:
        return None
    token = args[0].strip()
    if token.startswith("ref") and token[3:].isdigit():
        return int(token[3:])
    return None


def share_keyboard(lang: str, link: str) -> InlineKeyboardMarkup:
    """Telegram's native share sheet, prefilled with the user's invite link."""
    url = (
        "https://t.me/share/url?url=" + quote(link, safe="")
        + "&text=" + quote(t(lang, "share_text"), safe="")
    )
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "share_btn"), url=url)]]
    )


async def ensure_credits(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int
) -> bool:
    """The search-side gate: True → the search may run (and a successful one
    will cost 1 credit). False → an out-of-credits message with the user's
    invite link + share button was sent instead."""
    if is_owner(user_id):
        return True

    db = context.bot_data["db"]
    if await repo.get_credit_row(db, user_id) is None:
        await repo.enroll(db, user_id)  # texted without /start — same rules
    await repo.refill_if_due(db, user_id)

    row = await repo.get_credit_row(db, user_id)
    if row and row["credits"] > 0:
        return True

    lang = await repo.get_lang(db, user_id) or "en"
    link = ref_link(context.bot.username, user_id)
    due = (row["last_refill"] if row else 0) + config.REFILL_PERIOD
    hours = max(1, math.ceil((due - time.time()) / 3600))
    await context.bot.send_message(
        chat_id,
        t(lang, "out_of_credits", link=link, hours=hours),
        reply_markup=share_keyboard(lang, link),
        disable_web_page_preview=True,
    )
    logger.info("User %s is out of credits — blocked, refill in ~%dh", user_id, hours)
    return False


async def charge_on_success(
    context: ContextTypes.DEFAULT_TYPE, user_id: int
) -> int | None:
    """1 credit per search that found results. Returns the new balance, or
    None for the owner (no charge → no balance line in the results)."""
    if is_owner(user_id):
        return None
    return await repo.add_credits(context.bot_data["db"], user_id, -1)


async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/credits — balance, personal invite link and the rules, in their language."""
    user = update.effective_user
    db = context.bot_data["db"]
    lang = await repo.get_lang(db, user.id) or from_telegram_locale(user.language_code)

    if is_owner(user.id):
        await update.message.reply_text(t(lang, "credits_owner"))
        return

    await repo.refill_if_due(db, user.id)
    row = await repo.get_credit_row(db, user.id)
    balance = row["credits"] if row else 0
    link = ref_link(context.bot.username, user.id)
    await update.message.reply_text(
        t(lang, "credits_msg", n=balance, link=link),
        reply_markup=share_keyboard(lang, link),
        disable_web_page_preview=True,
        parse_mode="HTML",
    )


credits_handler = CommandHandler("credits", credits_command)
