"""Central configuration — everything the bot needs comes from .env"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing or invalid.\n"
        "Fix: create a file '.env' next to config.py containing:\n"
        "    BOT_TOKEN=your_token_from_BotFather"
    )

# Folders used by later steps (SQLite db, temporary PDF downloads)
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
TEMP_DIR = BASE_DIR / "tmp"
TEMP_DIR.mkdir(exist_ok=True)

# Force-subscribe gate (Step 6d): users must join this channel before the
# bot searches for them. The bot must be an ADMIN in the channel — Telegram
# only lets bots read member status of channels they administrate.
CHANNEL_USERNAME: str = os.getenv("CHANNEL_USERNAME", "@gifthubai").strip()
CHANNEL_URL: str = os.getenv("CHANNEL_URL", "https://t.me/gifthubai").strip()

# Credits & referral economy (Step 6e, user request):
#   «give every user 5 free credits and 2 credits every day … top up his
#   credits by sending their referral link … 1 credit for every invitation …
#   if he runs out of credits the bot doesnt work until he send the referral
#   link or wait 24h» — the owner account is exempt from credits (and from
#   the channel gate, so the operator can always test their own bot).
OWNER_ID: int = int(os.getenv("OWNER_ID", "8974969463"))
WELCOME_CREDITS: int = int(os.getenv("WELCOME_CREDITS", "5"))
DAILY_REFILL: int = int(os.getenv("DAILY_REFILL", "2"))
REFERRAL_BONUS: int = int(os.getenv("REFERRAL_BONUS", "1"))
REFILL_PERIOD: int = int(os.getenv("REFILL_PERIOD", str(24 * 60 * 60)))  # seconds
