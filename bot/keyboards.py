"""Inline keyboard builders."""
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# The chooser text itself is trilingual so it is understandable before any lang is set
LANG_BUTTONS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang:fr")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
    ]
)


def results_keyboard(results: list) -> tuple[str, InlineKeyboardMarkup]:
    """Numbered buttons [1]..[N] under the results list.

    Returns (cache_id, markup). The results themselves live in bot_data under
    cache_id — callback_data only carries `dl:<cache_id>:<index>` (tiny payload).
    """
    cache_id = uuid.uuid4().hex[:10]
    row = [
        InlineKeyboardButton(str(i + 1), callback_data=f"dl:{cache_id}:{i}")
        for i in range(len(results))
    ]
    return cache_id, InlineKeyboardMarkup([row]) if row else None
