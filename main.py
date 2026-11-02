"""
Maktabati (مكتبتي) — find free & legal PDFs by title (Arabic / French / English).
Step 5: real PDF delivery — tap → download → send → temp file deleted instantly.
"""
import logging

from telegram import Update
from telegram.ext import Application

import config
from bot.handlers.download import download_pick_handler
from bot.handlers.lang import lang_handler, lang_pick_handler
from bot.credits import credits_handler
from bot.handlers.search import sub_check_handler, text_handler
from bot.handlers.start import help_handler, start_handler
from db.database import close_db, init_db
from utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """Runs after Application is built, before polling starts."""
    await init_db(app)
    logger.info("SQLite ready at %s", config.DATA_DIR / "bookbot.db")

    # Brand the bot's public profile as "Maktabati" (Telegram display name,
    # start-screen description, about box). The @username can't be changed via API.
    try:
        await app.bot.set_my_name("Maktabati 📚")
        await app.bot.set_my_description(
            "أرسل عنوان كتاب واحصل على ملف PDF 📚 | "
            "Envoyez un titre, recevez le PDF | Send a title, get the PDF"
        )
        await app.bot.set_my_about_text(
            "Maktabati مكتبتي — free & legal book finder 📚 | الدعم / Support: @vxgix"
        )
        logger.info("Bot profile set: Maktabati")
    except Exception as exc:  # network hiccup must never block boot
        logger.warning("Could not set bot profile: %s", exc)


async def post_shutdown(app: Application) -> None:
    await close_db(app)
    logger.info("SQLite connection closed")


def main() -> None:
    setup_logging()
    logger.info("Starting Maktabati (Step 6e — credits & referrals, 4 sources, NL+cross-language search, channel gate)…")

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Commands first, then callbacks, then the catch-all text handler LAST
    app.add_handler(start_handler)
    app.add_handler(help_handler)
    app.add_handler(lang_handler)
    app.add_handler(lang_pick_handler)
    app.add_handler(download_pick_handler)
    app.add_handler(sub_check_handler)
    app.add_handler(credits_handler)
    app.add_handler(text_handler)

    logger.info("Bot is up — polling for updates…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
