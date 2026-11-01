"""Handlers: /lang command + language picker callback."""
import logging

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import bot.keyboards as keyboards
from bot.handlers.start import resolve_lang
from db import repo
from i18n.i18n import t

logger = logging.getLogger(__name__)


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/lang — show the trilingual language menu."""
    user = update.effective_user
    db = context.bot_data["db"]
    await repo.upsert_user(db, user.id, user.first_name, user.username)
    await update.message.reply_text(t("en", "choose_lang"), reply_markup=keyboards.LANG_BUTTONS)


async def on_lang_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User tapped a language button — save it and confirm in THAT language."""
    query = update.callback_query
    new_lang = query.data.split(":", 1)[1]

    user = update.effective_user
    db = context.bot_data["db"]
    await repo.upsert_user(db, user.id, user.first_name, user.username)
    await repo.set_lang(db, user.id, new_lang)

    await query.answer()
    await query.edit_message_text(t(new_lang, "lang_saved"))
    logger.info("User %s set language to %s", user.id, new_lang)


lang_handler = CommandHandler("lang", lang_command)
lang_pick_handler = CallbackQueryHandler(on_lang_pick, pattern=r"^lang:")
