"""Handlers: /start and /help."""
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import bot.keyboards as keyboards
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
    """/start — greet in the user's language; offer the language menu on first contact."""
    user = update.effective_user
    db = context.bot_data["db"]
    await repo.upsert_user(db, user.id, user.first_name, user.username)

    lang = await resolve_lang(update, context)
    await update.message.reply_text(t(lang, "start", name=user.first_name or "reader"))

    if not await repo.get_lang(db, user.id):  # first time → nudge the language menu
        await update.message.reply_text(t("en", "choose_lang"), reply_markup=keyboards.LANG_BUTTONS)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — commands, in the user's language."""
    lang = await resolve_lang(update, context)
    await update.message.reply_text(t(lang, "help"), parse_mode="HTML")


start_handler = CommandHandler("start", start)
help_handler = CommandHandler("help", help_command)
