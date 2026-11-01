"""Step 6b (user decisions): tap → verified DIRECT PDF LINK + the book's page.

User decisions stacked here:
• link-only delivery — no download/upload on the bot's side;
• every link VERIFIED (HEAD) before it is shown — the `{ia_id}.pdf` guess
  often 404s, so candidates go: pdf_url → source resolver (IA metadata real
  filename, Gutenberg alt pattern) → first URL answering 200 wins;
• «i should put direct link of pdf and direct link where he can find the
  pdf» — the success message carries BOTH the direct PDF link and the
  book's page link;
• a tap whose links all fail is no longer a dead end: the user gets the
  book's page link so the PDF can still be found there.

core/downloader.py stays in the codebase (unused) for possible file delivery.
"""
import logging

import httpx
from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from db import repo
from i18n.detect import detect_language
from i18n.i18n import t
from sources import REGISTRY

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Maktabati/0.5 (Telegram bot; open-access book finder)"}


async def _link_alive(url: str) -> bool:
    """True only if the server really serves this file (200 after redirects)."""
    try:
        async with httpx.AsyncClient(
            timeout=10, headers=_HEADERS, follow_redirects=True
        ) as client:
            resp = await client.head(url)
        if resp.status_code == 200:
            return True
        if resp.status_code in (404, 401, 403):   # missing or restricted → dead
            return False
        # some servers refuse HEAD → retry with a 1-byte GET
        async with httpx.AsyncClient(
            timeout=10, headers=_HEADERS, follow_redirects=True
        ) as client:
            resp = await client.get(url, headers={"Range": "bytes=0-0"})
        return resp.status_code in (200, 206)
    except httpx.HTTPError:
        return False  # un-reachable link counts as dead


async def _candidate_urls(book) -> list[str]:
    """pdf_url first, then whatever extra link the book's source can dig up
    at tap time (IA metadata real filename, Gutenberg alternate pattern, …)."""
    candidates: list[str] = [book.pdf_url] if book.pdf_url else []
    for source in REGISTRY:
        if source.name == book.source:
            try:
                extra = await source.resolve(book)
            except Exception as exc:  # noqa: BLE001 — a resolver failing must not kill the tap
                logger.warning("resolver %s failed: %s: %s",
                               source.name, exc.__class__.__name__, exc)
                extra = ""
            if extra and extra not in candidates:
                candidates.append(extra)
            break
    return candidates


async def on_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, cache_id, idx = query.data.split(":")
    user = update.effective_user
    db = context.bot_data["db"]
    msg_text = query.message.text if query.message else ""
    lang = await repo.get_lang(db, user.id) or detect_language(msg_text) or "en"

    results = context.bot_data.get("results_cache", {}).get(cache_id)
    if not results or int(idx) >= len(results):
        await query.answer(t(lang, "expired"), show_alert=True)
        return

    book = results[int(idx)]
    await query.answer()  # stop Telegram's spinner right away

    url = ""
    for candidate in await _candidate_urls(book):
        if await _link_alive(candidate):
            url = candidate
            break
        logger.info("Dead link skipped (%s…) for %r", candidate[:60], book.title[:50])
    if not url:
        # User decision: never a dead end — point to the book's page instead.
        page = (book.page_url or "").strip()
        if page:
            await context.bot.send_message(
                update.effective_chat.id,
                t(lang, "err_no_pdf_page", url=page),
                disable_web_page_preview=True,
            )
        else:
            await context.bot.send_message(update.effective_chat.id, t(lang, "err_no_pdf"))
        return

    pdf_note = t(lang, "picked_pdf", url=url)
    if (book.page_url or "").strip():  # user decision: direct link + where-to-find link
        pdf_note += "\n" + t(lang, "picked_page", url=book.page_url)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t(lang, "picked", title=book.title[:120], source=book.source, pdf_note=pdf_note),
        disable_web_page_preview=True,
    )
    logger.info("User %s picked %r (%s) → verified link",
                user.id, book.title[:60], book.source)


download_pick_handler = CallbackQueryHandler(on_pick, pattern=r"^dl:")
