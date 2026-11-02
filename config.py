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
