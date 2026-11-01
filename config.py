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
