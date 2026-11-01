"""Language detection — no external dependency, script + keyword heuristics."""
import re

# Arabic blocks: standard, supplement, extended-A, presentation forms
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

# Very common standalone French words (works well on titles & short phrases)
_FRENCH_HINTS = re.compile(
    r"\b(le|la|les|des|une|un|du|de|d'|l'|et|livre|bonjour|salut|merci|cherche|recherche|pour)\b",
    re.IGNORECASE,
)

_FRENCH_ACCENTS = set("éèêëàâçôöûùüîïœÉÈÊËÀÂÇÔÖÛÙÜÎÏŒ")


def detect_language(text: str) -> str:
    """Guess 'ar' / 'fr' / 'en' from the text of a message. Defaults to 'en'."""
    if not text:
        return "en"
    if _ARABIC_RE.search(text):
        return "ar"
    if any(ch in _FRENCH_ACCENTS for ch in text):
        return "fr"
    if _FRENCH_HINTS.search(text):
        return "fr"
    return "en"


def from_telegram_locale(code: str | None) -> str:
    """Map a Telegram client language_code (e.g. 'ar-DZ', 'fr-FR') to a supported lang."""
    if not code:
        return "en"
    base = code.split("-")[0].lower()
    return base if base in ("ar", "fr", "en") else "en"
