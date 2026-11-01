"""Text normalization — mostly for Arabic queries (diacritics, hamza variants, tatweel)."""
import re

# harakat/fatha/damma/kasra, sukun, shadda, dagger alif, tatweel
_DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ALEF_RE = re.compile(r"[إأآٱا]")
# strip punctuation but keep word characters and the Arabic block
_PUNCT_RE = re.compile(r"[^\w\s\u0600-\u06FF]", re.UNICODE)


def normalize_arabic(text: str) -> str:
    """Normalize Arabic spelling variants so searches match more editions."""
    text = _DIACRITICS_RE.sub("", text)      # remove تشكيل
    text = _ALEF_RE.sub("ا", text)           # unify alef forms
    text = text.replace("ى", "ي")            # alef maqsura → ya
    text = text.replace("ة", "ه")            # ta marbuta → ha
    text = text.replace("ؤ", "و").replace("ئ", "ي")
    return text


def normalize_query(text: str) -> str:
    """Full pipeline for a user-typed search query (any language)."""
    text = normalize_arabic(text)
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.lower().split())
