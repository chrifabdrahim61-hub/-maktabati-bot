"""Cross-language search fallback (Step 6c).

User report (the real issue): «العادات الذرية» → nothing, while "atomic
habits" → 5 scans. Legal catalogs index books under their ORIGINAL title
(usually English); an Arabic edition title can't reach those entries.
So on a total miss the bot translates the cleaned query once and retries.

Providers (in order, both keyless):
1. MyMemory — api.mymemory.translated.net, free anonymous ~5000 chars/day/IP
2. Google "gtx" endpoint — translate.googleapis.com/translate_a/single
   (same engine as translate.google.com, auto-detects the source language)

Every call is cached (bounded) and every failure returns "" — the search
then simply behaves like before (no_results). Parsing is factored into pure
functions so tests run without network.
"""
import logging

import httpx

from i18n.detect import detect_language

logger = logging.getLogger(__name__)

_TIMEOUT = 10
_HEADERS = {"User-Agent": "Maktabati/0.6 (Telegram bot; open-access book finder)"}

_cache: dict[tuple[str, str], str] = {}
_CACHE_MAX = 300


def _cache_put(key: tuple[str, str], value: str) -> None:
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[key] = value


def _mymemory_parse(data: dict) -> str:
    """MyMemory JSON → text ('' on quota warnings / junk)."""
    translated = (data.get("responseData") or {}).get("translatedText") or ""
    if not translated or "MYMEMORY WARNING" in translated.upper():
        return ""  # quota exhausted or error text — not a translation
    return translated.strip()


def _gtx_parse(data: list) -> str:
    """Google gtx nested-array JSON → concatenated translation segments."""
    try:
        segments = data[0] or []
        return "".join(seg[0] for seg in segments if seg and seg[0]).strip()
    except (TypeError, IndexError, KeyError):
        return ""


async def _mymemory(text: str, source: str, target: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text, "langpair": f"{source}|{target}"},
            )
            resp.raise_for_status()
            return _mymemory_parse(resp.json())
    except Exception as exc:  # noqa: BLE001 — translation is best-effort
        logger.warning("MyMemory failed: %s: %s", exc.__class__.__name__, exc)
        return ""


async def _gtx(text: str, target: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(
                "https://translate.googleapis.com/translate_a/single",
                params={"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text},
            )
            resp.raise_for_status()
            return _gtx_parse(resp.json())
    except Exception as exc:  # noqa: BLE001
        logger.warning("gtx failed: %s: %s", exc.__class__.__name__, exc)
        return ""


async def translate_text(text: str, target: str, source: str) -> str:
    """Translate `text` into `target`; '' when both providers fail."""
    text = (text or "").strip()
    if not text or not target or source == target:
        return ""
    key = (text, target)
    if key in _cache:
        return _cache[key]
    out = await _mymemory(text, source, target) or await _gtx(text, target)
    _cache_put(key, out)
    if out:
        logger.info("Translated %r → %r", text[:50], out[:60])
    return out


def fallback_target(cleaned: str, user_lang: str) -> tuple[str, str]:
    """(source, target) for the cross-language retry, or ('','') to skip.

    • Arabic / French query → English  (catalogs index the original titles)
    • English query from an Arabic user → Arabic  (find the Arabic scan)
    """
    q_lang = detect_language(cleaned)
    if q_lang == "en":
        return ("en", "ar") if user_lang == "ar" else ("", "")
    return (q_lang, "en")
