"""Handlers: /start and /help."""
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import bot.keyboards as keyboards
from bot.credits import is_owner, parse_ref
from bot.handlers.subscribe import check_and_cache, join_keyboard
from db import repo
from i18n.detect import from_telegram_locale
from i18n.i18n import t

logger = logging.getLogger(__name__)


async def resolve_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Language priority: explicit choice in DB → Telegram client language → English."""
    user = update.effective_user
    db = context.bot_data["db"]
    saved = await repo.get_lang(db, user.id)
    if saved:
        return saved
    return from_telegram_locale(user.language_code)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — greet in the user's language; offer the language menu on first
    contact; process referral deep-links (t.me/<bot>?start=ref<user_id>)."""
    user = update.effective_user
    db = context.bot_data["db"]

    ref = parse_ref(context.args)
    if ref == user.id:  # nobody earns credits by inviting themselves
        ref = None
    created = await repo.upsert_user(
        db, user.id, user.first_name, user.username, referred_by=ref
    )

    lang = await resolve_lang(update, context)
    await update.message.reply_text(t(lang, "start", name=user.first_name or "reader"))

    if not await repo.get_lang(db, user.id):  # first time → nudge the language menu
        await update.message.reply_text(t("en", "choose_lang"), reply_markup=keyboards.LANG_BUTTONS)

    # Force-subscribe prompt right under the greeting (Step 6d)
    if not await check_and_cache(context, user.id):
        await update.message.reply_text(
            t(lang, "join_channel"), reply_markup=join_keyboard(lang)
        )

    # Referral reward (Step 6e): +1 credit to the friend whose link brought
    # this NEW user in. Granted on first /start even if the invitee then hits
    # the channel gate — the invitation itself already happened.
    if created and ref and not is_owner(user.id):
        balance = await repo.reward_referral(db, ref, user.id)
        if balance is not None:
            ref_lang = await repo.get_lang(db, ref) or "en"
            try:
                await context.bot.send_message(
                    ref,
                    t(ref_lang, "ref_bonus", name=user.first_name or "A reader", n=balance),
                )
            except Exception as exc:  # referrer blocked the bot — never crash onboarding
                logger.info("Referral notify to %s failed: %s", ref, exc)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — commands, in the user's language."""
    lang = await resolve_lang(update, context)
    await update.message.reply_text(t(lang, "help"), parse_mode="HTML")


start_handler = CommandHandler("start", start)
help_handler = CommandHandler("help", help_command)
