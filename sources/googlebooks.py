"""Google Books — free full-text PDFs only (public-domain, ALL_PAGES viewability).

API: googleapis.com/books/v1/volumes (no key needed, generous anonymous quota).
A result ships only when Google itself offers a direct PDF download link —
preview-only / DRM (acsTokenLink) volumes are skipped.
"""
import logging

import httpx

from core.models import BookResult
from sources.base import BookSource

_API = "https://www.googleapis.com/books/v1/volumes"
_HEADERS = {"User-Agent": "Maktabati/0.5 (Telegram bot; open-access book finder)"}

logger = logging.getLogger(__name__)


def intitle_terms(query: str) -> str:
    """AND one intitle: operator per token (Step 6b).

    `intitle:"art of war"` is a strict phrase; `intitle:art intitle:war`
    accepts any word order / extra words — the natural-language behaviour
    the user asked for. Single-char tokens are dropped (noise).
    """
    tokens = [t for t in query.split() if len(t) >= 2]
    if not tokens:
        tokens = query.split()
    return " ".join(f"intitle:{t}" for t in tokens)


class GoogleBooksSource(BookSource):
    name = "Google Books"

    async def search(self, query: str, limit: int = 5) -> list[BookResult]:
        params = {
            "q": intitle_terms(query),
            "maxResults": min(max(limit * 2, 8), 16),
            "printType": "books",
        }
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(_API, params=params)
            resp.raise_for_status()
            items = resp.json().get("items", []) or []
        return self._parse_items(items, limit, source_name=self.name)

    @staticmethod
    def _parse_items(items: list[dict], limit: int = 5, source_name: str = "Google Books") -> list[BookResult]:
        results: list[BookResult] = []
        for it in items:
            vol = it.get("volumeInfo", {}) or {}
            access = it.get("accessInfo", {}) or {}
            pdf = access.get("pdf", {}) or {}

            download = pdf.get("downloadLink") or ""
            if access.get("viewability") != "ALL_PAGES" or not pdf.get("isAvailable") or not download:
                continue  # preview / DRM-only → not a real free PDF

            authors = vol.get("authors") or []
            year = str(vol.get("publishedDate", "") or "")[:4]
            results.append(
                BookResult(
                    title=(vol.get("title") or "").strip(),
                    author=", ".join(authors) or "—",
                    year=year,
                    source=source_name,
                    lang=vol.get("language", ""),
                    pdf_url=download,
                    page_url=vol.get("infoLink") or vol.get("previewLink") or "",
                    detail={"viewability": access.get("viewability", "")},
                )
            )
        return results[:limit]
