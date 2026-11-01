"""Project Gutenberg — public-domain classics (strong for FR/EN).

API: gutendex.com. Prefer the catalogued application/pdf format; otherwise
Gutenberg auto-generates PDFs at /ebooks/{id}.pdf.noimages — the tap-time
HEAD check in the delivery handler confirms whichever candidate is alive.
"""
import logging
import re

import httpx

from core.models import BookResult
from sources.base import BookSource

_API = "https://gutendex.com/books/"
_HEADERS = {"User-Agent": "Maktabati/0.5 (Telegram bot; open-access book finder)"}

logger = logging.getLogger(__name__)


def _clean_author(name: str) -> str:
    """'Tzu, Sun' stays; 'Conrad, Joseph, 1859-1924' → 'Conrad, Joseph';
    'Sunzi, active 5th century B.C.' → 'Sunzi'."""
    name = re.split(r",\s*\d{3,}", name)[0]                # death dates
    name = re.split(r",\s*active\b", name, flags=re.IGNORECASE)[0]
    return name.strip() or name.strip()


class GutenbergSource(BookSource):
    name = "Project Gutenberg"

    async def search(self, query: str, limit: int = 5) -> list[BookResult]:
        params = {"search": query}
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(_API, params=params)
            resp.raise_for_status()
            rows = resp.json().get("results", []) or []
        return self._parse_rows(rows, limit, source_name=self.name)

    @staticmethod
    def _parse_rows(rows: list[dict], limit: int = 5, source_name: str = "Project Gutenberg") -> list[BookResult]:
        results: list[BookResult] = []
        for row in rows:
            gid = row.get("id", 0)
            if not gid:
                continue
            formats = row.get("formats", {}) or {}
            pdf = formats.get("application/pdf") or f"https://www.gutenberg.org/ebooks/{gid}.pdf.noimages"
            authors = row.get("authors") or []
            langs = row.get("languages") or [""]
            results.append(
                BookResult(
                    title=(row.get("title") or "").strip(),
                    author=_clean_author(authors[0]["name"]) if authors else "—",
                    year="",
                    source=source_name,
                    lang=langs[0],
                    pdf_url=pdf,
                    gutenberg_id=gid,
                    page_url=f"https://www.gutenberg.org/ebooks/{gid}",
                    detail={"translations": len(row.get("translators", []) or [])},
                )
            )
        return results[:limit]

    async def resolve(self, result: BookResult) -> str:
        """Tap-time second candidate: the other PDF pattern Gutenberg serves."""
        if not result.gutenberg_id:
            return ""
        gid = result.gutenberg_id
        alt = (f"https://www.gutenberg.org/ebooks/{gid}.pdf.images"
               if not result.pdf_url.endswith(".pdf.images")
               else f"https://www.gutenberg.org/ebooks/{gid}.pdf.noimages")
        return alt
