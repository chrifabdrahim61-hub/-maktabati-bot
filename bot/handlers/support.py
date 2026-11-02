"""Step 6f: 🤍 support button → Telegram Stars donations (user request).

«now i want to set in the output after giving the book pdf or the source
setting a small button of support the bot with a white heart when clicking
it it shows donations with stars 25/50/75/100 ect»

Revision (user): «in the output i dont want just a heart a text too» — the
button now reads 🤍 Support Maktabati (support_heart, localized); and
«i want the bot have a small commands list button which contains start,
credits, donate and necessary things» — build_commands() + set_my_commands()
in main.py puts /start /help /lang /credits /donate /privacy into the ≡
menu button, /donate opens this menu directly, /privacy shows the policy.

Flow: every delivered book message (the verified PDF link or the source-page
fallback in handlers/download.py) carries the small 🤍 text button. Tapping
it opens the donation menu with one ⭐ button per STAR_TIERS entry
(25/50/75/100/250). A tier tap sends a Telegram Stars invoice — currency
"XTR", which needs NO payment provider token; Telegram renders the in-chat
payment sheet itself. PreCheckoutQuery is auto-approved, and a successful
payment earns a trilingual thank-you plus a row in the donations table
(for the later /stats step).
"""
import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

import config
from db import repo
from i18n.detect import detect_language
from i18n.i18n import t

logger = logging.getLogger(__name__)


def heart_keyboard(lang: str) -> InlineKeyboardMarkup:
    """The little 🤍 button attached to delivered book messages."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "support_heart"), callback_data="stars:menu")]]
    )


def donate_keyboard(lang: str) -> InlineKeyboardMarkup:
    """One ⭐ button per tier (two per row) + a ✖️ close button."""
    rows, row = [], []
    for n in config.STAR_TIERS:
        row.append(InlineKeyboardButton(f"{n} ⭐", callback_data=f"stars:pay:{n}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t(lang, "close_btn"), callback_data="stars:close")])
    return InlineKeyboardMarkup(rows)


async def on_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Router for the stars: callbacks — menu / pay:<n> / close."""
    query = update.callback_query
    data = query.data or ""
    db = context.bot_data["db"]
    user = update.effective_user
    msg_text = query.message.text if query.message else ""
    lang = await repo.get_lang(db, user.id) or detect_language(msg_text) or "en"

    if data == "stars:menu":
        await query.answer()
        await context.bot.send_message(
            update.effective_chat.id,
            t(lang, "donate_menu"),
            reply_markup=donate_keyboard(lang),
        )
        logger.info("User %s opened the donation menu", user.id)

    elif data.startswith("stars:pay:"):
        try:
            amount = int(data.split(":")[2])
        except (IndexError, ValueError):
            amount = 0
        if amount not in config.STAR_TIERS:  # no arbitrary payloads
            await query.answer(t(lang, "error_generic"), show_alert=True)
            return
        await query.answer()
        try:
            await context.bot.send_invoice(
                chat_id=update.effective_chat.id,
                title=t(lang, "donate_title"),
                description=t(lang, "donate_desc", n=amount),
                payload=f"donation:{amount}",
                currency="XTR",  # Telegram Stars — provider_token stays empty
                prices=[LabeledPrice(label=t(lang, "donate_title"), amount=amount)],
            )
            logger.info("Stars invoice sent: user %s → %d ⭐", user.id, amount)
        except TelegramError as exc:
            logger.warning("send_invoice failed for %s: %s", user.id, exc)
            await context.bot.send_message(update.effective_chat.id, t(lang, "donate_err"))

    elif data == "stars:close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:  # already gone / too old to edit
            pass


async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/donate — open the Stars donation menu directly, in their language."""
    user = update.effective_user
    db = context.bot_data["db"]
    lang = await repo.get_lang(db, user.id) or "en"
    await update.message.reply_text(
        t(lang, "donate_menu"), reply_markup=donate_keyboard(lang)
    )
    logger.info("User %s opened /donate", user.id)


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/privacy — what the bot stores, what it never does (trilingual)."""
    user = update.effective_user
    db = context.bot_data["db"]
    lang = await repo.get_lang(db, user.id) or "en"
    await update.message.reply_text(
        t(lang, "privacy_text"), parse_mode="HTML", disable_web_page_preview=True
    )


def build_commands(lang: str) -> list[BotCommand]:
    """The localized command list behind the ≡ menu button next to the
    input field — Telegram shows the matching language automatically."""
    return [
        BotCommand("start", t(lang, "cmd_start")),
        BotCommand("help", t(lang, "cmd_help")),
        BotCommand("lang", t(lang, "cmd_lang")),
        BotCommand("credits", t(lang, "cmd_credits")),
        BotCommand("donate", t(lang, "cmd_donate")),
        BotCommand("privacy", t(lang, "cmd_privacy")),
    ]


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve every Stars checkout — nothing to validate for donations."""
    await update.pre_checkout_query.answer(ok=True)


async def on_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    payment = update.message.successful_payment
    db = context.bot_data["db"]
    await repo.log_donation(db, user.id, payment.total_amount, payment.invoice_payload)
    lang = await repo.get_lang(db, user.id) or "en"
    await update.message.reply_text(
        t(lang, "donate_thanks", name=user.first_name or "friend", n=payment.total_amount)
    )
    logger.info("Donation received: user %s paid %d %s (%s)",
                user.id, payment.total_amount, payment.currency, payment.invoice_payload)


stars_handler = CallbackQueryHandler(on_stars, pattern=r"^stars:")
donate_handler = CommandHandler("donate", donate_command)
privacy_handler = CommandHandler("privacy", privacy_command)
precheckout_handler = PreCheckoutQueryHandler(precheckout)
payment_handler = MessageHandler(filters.SUCCESSFUL_PAYMENT, on_payment)
