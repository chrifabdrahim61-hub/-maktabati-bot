"""Tiny i18n helper — loads ar/fr/en JSON dictionaries once at import."""
import json
from pathlib import Path

SUPPORTED = ("ar", "fr", "en")
DEFAULT = "en"

_LOCALES: dict[str, dict[str, str]] = {}
for _file in Path(__file__).parent.glob("*.json"):
    _LOCALES[_file.stem] = json.loads(_file.read_text(encoding="utf-8"))


def t(lang: str, key: str, **kwargs) -> str:
    """Translate `key` into `lang` (falls back to English, then to the key itself)."""
    lang = lang if lang in SUPPORTED else DEFAULT
    text = _LOCALES.get(lang, {}).get(key) or _LOCALES[DEFAULT].get(key) or key
    return text.format(**kwargs) if kwargs else text
