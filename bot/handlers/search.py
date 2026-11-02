"""Step 6c: natural-language + cross-language search → merge & rank → buttons.

User requests baked in here:
  • «he shouldnt enter the right name exactly … a gap of natural language» —
    the raw message is cleaned by core/nl.py before searching («ابي كتاب
    الداء والدواء» → «الداء والدواء»), then relaxed keyword variants retry
    on a miss (core/nl.search_variants).
  • THE REAL ISSUE the user found: «العادات الذرية» → nothing while
    "atomic habits" → 5 scans. Legal catalogs index books under their
    ORIGINAL (mostly English) titles. So after a total miss the handler
    translates the query once (core/translate.py) and searches again —
    Arabic/French titles reach English entries, English queries from
    Arabic users reach Arabic scans. A small note under the header tells
    the user which wording produced the results.
  • «in some books there is only one source» — top-6 results, every source
    queried in parallel with an individual timeout so one slow or blocked
    source can never stall (or kill) the whole search.
  • Step 6d force-subscribe: non-members of the channel get the join prompt
    instead of results; after they join and tap «✅ Check» their pending
    search resumes automatically.
PDF delivery on tap is in handlers/download.py (Step 5/6b).
"""
import asyncio
import logging
from html import escape

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from bot.handlers.subscribe import ensure_subscribed, is_member
from bot.keyboards import results_keyboard
from core.nl import clean_query, search_variants
from core.ranker import rank_results
from core.translate import fallback_target, translate_text
from db import repo
from i18n.detect import detect_language
from i18n.i18n import t
from sources import REGISTRY

logger = logging.getLogger(__name__)

CACHE_MAX = 40        # how many recent result-sets to keep in memory
SOURCE_TIMEOUT = 15   # seconds per source — one slow site can't stall the rest
RESULTS_SHOWN = 6     # more buttons = more chances one link actually works


def _cache_put(context: ContextTypes.DEFAULT_TYPE, results: list, cache_id: str) -> None:
    """Store results under the SAME cache_id that results_keyboard() baked into
    the buttons. Generating a second id here was the "expired" bug."""
    cache = context.bot_data.setdefault("results_cache", {})
    cache[cache_id] = results
    while len(cache) > CACHE_MAX:  # bounded memory: drop oldest
        cache.pop(next(iter(cache)))


def _deliverable(results: list) -> list:
    """Only results that can actually deliver a PDF — kills most "no PDF" taps
    (tap-time HEAD verification may still veto individual links, and the tap
    handler then falls back to the book's page link)."""
    return [r for r in results if r.pdf_url or r.ia_id or r.gutenberg_id]


async def _source_search(source, query: str, limit: int) -> list:
    """One source, one timeout, zero exceptions leaking out."""
    try:
        return await asyncio.wait_for(source.search(query, limit=limit), timeout=SOURCE_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — a broken source must not kill the search
        logger.warning("Source %s failed on %r: %s: %s",
                       source.name, query[:60], exc.__class__.__name__, exc)
        return []


async def _search_all(query: str, limit: int) -> list:
    payload = await asyncio.gather(*(_source_search(s, query, limit) for s in REGISTRY))
    return [r for sub in payload for r in sub]


async def run_search(cleaned: str, user_lang: str) -> tuple[list, str, bool]:
    """The full attempt ladder. Returns (ranked, winning_attempt, translated).

    1. cleaned query  2. relaxed keyword variants (top-3, top-2 tokens)
    3. cross-language retry: translate once, then its top variant.
    Each stage only runs when the previous one found nothing.
    """
    for attempt in [cleaned] + [v for v in search_variants(cleaned) if v != cleaned]:
        flat = await _search_all(attempt, limit=8)
        ranked = rank_results(attempt, _deliverable(flat), limit=RESULTS_SHOWN)
        if ranked:
            return ranked, attempt, False
        logger.info("0 hits for %r — trying looser variant", attempt[:60])

    # Cross-language retry (Step 6c): an edition title can't reach entries
    # catalogued under the original title (العادات الذرية ↔ atomic habits).
    src_lang, tgt = fallback_target(cleaned, user_lang)
    if tgt:
        translated = await translate_text(cleaned, tgt, src_lang)
        translated = clean_query(translated) if translated else ""
        if translated and translated != cleaned:
            logger.info("Cross-language retry: %r → %r", cleaned[:40], translated[:60])
            for attempt in [translated] + search_variants(translated)[:1]:
                flat = await _search_all(attempt, limit=8)
                ranked = rank_results(attempt, _deliverable(flat), limit=RESULTS_SHOWN)
                if ranked:
                    return ranked, attempt, True
    return [], "", False


async def do_search(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, raw: str) -> None:
    """The full search pipeline — shared by on_text and the sub:check button."""
    db = context.bot_data["db"]
    lang = await repo.get_lang(db, user_id) or detect_language(raw)

    # Natural-language pass: «ابي كتاب فن الحرب شكرا» → «فن الحرب»
    cleaned = clean_query(raw) or raw

    bot = context.bot
    status = await bot.send_message(chat_id, t(lang, "searching", title=raw[:80]))

    ranked, used, translated_mode = await run_search(cleaned, lang)

    if not ranked:
        await status.edit_text(t(lang, "no_results", title=raw[:80]))
        return

    cache_id, markup = results_keyboard(ranked)
    _cache_put(context, ranked, cache_id)

    lines = [t(lang, "results_header", title=raw[:60])]
    if translated_mode:
        lines.append(t(lang, "via_translation", query=used[:60]))
    lines.append("")
    for i, r in enumerate(ranked, 1):
        year = f" ({r.year})" if r.year else ""
        badge = " ⏬" if r.pdf_url else ""  # direct download available
        lines.append(
            f"{i}. <b>{escape(r.title)}</b>{badge}\n"
            f"    ✍️ {escape(r.author)}{year} • 📚 {escape(r.source)}"
        )
    lines.append("")
    lines.append(f"👇 {t(lang, 'pick_below')}")

    await status.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup,
    )
    logger.info(
        "User %s searched %r (cleaned %r%s) → %d ranked",
        user_id, raw[:60], used[:60], ", translated" if translated_mode else "", len(ranked),
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    raw = update.message.text.strip()

    # Force-subscribe gate (Step 6d): non-members get the join prompt.
    if not await ensure_subscribed(update, context):
        context.bot_data.setdefault("sub_pending", {})[user.id] = raw
        return

    await do_search(context, update.effective_chat.id, user.id, raw)


async def on_sub_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«✅ Check» button after joining the channel — re-verify, resume search."""
    query = update.callback_query
    user = update.effective_user
    db = context.bot_data["db"]
    lang = await repo.get_lang(db, user.id) or "en"

    if not await is_member(context.bot, user.id):
        await query.answer(t(lang, "join_channel"), show_alert=True)
        return

    context.bot_data.setdefault("sub_ok", set()).add(user.id)
    pending = context.bot_data.setdefault("sub_pending", {}).pop(user.id, None)
    await query.answer()
    try:
        await query.edit_message_text(t(lang, "join_ok"))
    except BadRequest:  # e.g. the message was deleted meanwhile
        pass
    logger.info("User %s verified subscription%s",
                user.id, " — resuming pending search" if pending else "")
    if pending:
        await do_search(context, update.effective_chat.id, user.id, pending)


text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, on_text)
sub_check_handler = CallbackQueryHandler(on_sub_check, pattern=r"^sub:")
