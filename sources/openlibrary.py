"""Open Library (openlibrary.org) — free & legal, exposes IA scans of public-domain books."""
import logging

import httpx

from core.models import BookResult
from sources.base import BookSource

_API = "https://openlibrary.org/search.json"
_HEADERS = {"User-Agent": "Maktabati/0.5 (Telegram bot; open-access book finder)"}

logger = logging.getLogger(__name__)


class OpenLibrarySource(BookSource):
    name = "Open Library"

    async def search(self, query: str, limit: int = 5) -> list[BookResult]:
        params = {
            "q": query,
            "limit": min(max(limit * 2, 8), 16),  # fetch extra, keep the best
            "fields": "key,title,author_name,first_publish_year,ia,language,ebook_access",
        }
        async with httpx.AsyncClient(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(_API, params=params)
            resp.raise_for_status()
            docs = resp.json().get("docs", [])
        return self._parse_docs(docs, limit, source_name=self.name)

    @staticmethod
    def _parse_docs(docs: list[dict], limit: int = 5, source_name: str = "Open Library") -> list[BookResult]:
        """Map raw search.json docs to BookResult (separated for unit testing)."""
        results: list[BookResult] = []
        for doc in docs:
            ia_ids = doc.get("ia") or []
            access = doc.get("ebook_access", "")  # public | borrowable | printdisabled | no_ebook
            key = doc.get("key", "")
            results.append(
                BookResult(
                    title=(doc.get("title") or "Untitled").strip(),
                    author=", ".join(doc.get("author_name") or []) or "—",
                    year=doc.get("first_publish_year") or "",
                    source=source_name,
                    lang=(doc.get("language") or [""])[0],
                    # public-domain scans can be fetched directly; borrowable cannot
                    pdf_url=(
                        f"https://archive.org/download/{ia_ids[0]}/{ia_ids[0]}.pdf"
                        if ia_ids and access == "public"
                        else ""
                    ),
                    openlibrary_id=key.split("/")[-1],
                    ia_id=ia_ids[0] if ia_ids else "",
                    page_url=f"https://openlibrary.org{key}" if key else "",
                    detail={"ebook_access": access},
                )
            )
        return results[:limit]
