"""Force-subscribe gate (Step 6d, user request).

«i want to make an update and its to subscribe in the channel
t.me/gifthubai and verify the subscription then he can access and run the
bot normally».

Flow: a search from a non-member gets the join prompt (URL button to the
channel + «✅ Check» button). The user joins, taps Check, the bot re-asks
Telegram via getChatMember — only real members pass, and their pending
search resumes automatically (handled in handlers/search.py).

Fail-open policy (the bot must never brick itself):
  • bot is not admin / not in the channel → Telegram refuses getChatMember;
    we log ONE loud warning and let people through (gate auto-disables
    until the bot is made admin in the channel);
  • transient Telegram/network errors → let the request through;
  • a definitive "not a participant" answer → not a member.
Verified members are cached in bot_data for the process lifetime
(restart = re-verify), so normal searches cost zero extra API calls.
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

import config
from db import repo
from i18n.detect import detect_language
from i18n.i18n import t

logger = logging.getLogger(__name__)

_OK_STATUSES = {"member", "administrator", "creator"}
_warned_no_admin = False  # warn once per process, not per search


def join_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Channel URL button + the verify callback button."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "sub_join_btn"), url=config.CHANNEL_URL)],
            [InlineKeyboardButton(t(lang, "sub_check_btn"), callback_data="sub:check")],
        ]
    )


async def is_member(bot, user_id: int) -> bool:
    """True only if Telegram says user_id is in the channel (see fail-open notes)."""
    global _warned_no_admin
    try:
        member = await bot.get_chat_member(chat_id=config.CHANNEL_USERNAME, user_id=user_id)
    except BadRequest as exc:
        text = str(exc).lower()
        if "participant" in text or "user not found" in text:
            return False  # definitive: this user is not in the channel
        if not _warned_no_admin:
            _warned_no_admin = True
            logger.warning(
                "SUBSCRIBE GATE DISABLED — Telegram refused getChatMember (%s). "
                "Fix: add this bot as an ADMIN in %s, then restart.",
                exc, config.CHANNEL_USERNAME,
            )
        return True   # setup problem, not the user's fault → fail open
    except TelegramError as exc:  # timeouts, network hiccups…
        logger.warning("get_chat_member failed (%s) — allowing this request", exc)
        return True

    status = getattr(member, "status", "")
    if status == "restricted":  # restricted members may still be members
        return bool(getattr(member, "is_member", False))
    return status in _OK_STATUSES


async def check_and_cache(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Membership with a process-lifetime cache (one API call per user per run)."""
    ok_set = context.bot_data.setdefault("sub_ok", set())
    if user_id in ok_set:
        return True
    if await is_member(context.bot, user_id):
        ok_set.add(user_id)
        return True
    return False


async def ensure_subscribed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Gate for the search handler: True → proceed; False → prompt sent."""
    user = update.effective_user
    if await check_and_cache(context, user.id):
        return True

    db = context.bot_data["db"]
    lang = await repo.get_lang(db, user.id) or detect_language(update.message.text or "")
    await update.message.reply_text(
        t(lang, "join_channel"),
        reply_markup=join_keyboard(lang),
        disable_web_page_preview=True,
    )
    logger.info("User %s not subscribed to %s — gated", user.id, config.CHANNEL_USERNAME)
    return False
