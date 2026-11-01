"""Internet Archive (archive.org) — search public text scans directly (PDF-friendly)."""
import logging
from urllib.parse import quote

import httpx

from core.models import BookResult
from sources.base import BookSource

_API = "https://archive.org/advancedsearch.php"
_METADATA = "https://archive.org/metadata/{ia_id}"
_HEADERS = {"User-Agent": "Maktabati/0.5 (Telegram bot; open-access book finder)"}

logger = logging.getLogger(__name__)


def title_clause(query: str) -> str:
    """Lucene clause that ANDs the title tokens (Step 6b).

    The old `title:("full query")` was an EXACT PHRASE match — «الداء والدواء
    لابن القيم» failed whenever the catalog title wasn't word-for-word
    identical, which is most of the time in natural language. ANDing tokens
    matches any word order and partial titles: title:(الداء AND والدواء).
    """
    tokens = query.split()
    if not tokens:
        return ""
    return "title:(" + " AND ".join(tokens) + ")"


class InternetArchiveSource(BookSource):
    name = "Internet Archive"

    async def search(self, query: str, limit: int = 5) -> list[BookResult]:
        clause = title_clause(query)
        if not clause:
            return []
        params = {
            "q": f"{clause} AND mediatype:texts",
            "fl[]": ["identifier", "title", "creator", "year", "language", "licenseurl"],
            "rows": min(max(limit * 2, 8), 14),
            "output": "json",
            "sort[]": "downloads desc",  # popularity ≈ quality signal
        }
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(_API, params=params)
            resp.raise_for_status()
            docs = resp.json().get("response", {}).get("docs", [])
        return self._parse_docs(docs, limit, source_name=self.name)

    @staticmethod
    def _parse_docs(docs: list[dict], limit: int = 5, source_name: str = "Internet Archive") -> list[BookResult]:
        results: list[BookResult] = []
        for doc in docs:
            identifier = doc.get("identifier", "")
            if not identifier:
                continue
            creator = doc.get("creator") or []
            if isinstance(creator, str):
                creator = [creator]
            language = doc.get("language") or ""
            if isinstance(language, list):
                language = language[0] if language else ""
            license_url = doc.get("licenseurl") or ""
            results.append(
                BookResult(
                    title=(doc.get("title") or identifier).strip(),
                    author=", ".join(creator) or "—",
                    year=doc.get("year") or "",
                    source=source_name,
                    lang=language,
                    # candidate link — Step 5 verifies with HEAD before sending
                    pdf_url=f"https://archive.org/download/{identifier}/{identifier}.pdf",
                    ia_id=identifier,
                    page_url=f"https://archive.org/details/{identifier}",
                    detail={"license": license_url, "public_domain": "publicdomain" in license_url},
                )
            )
        return results[:limit]


    async def resolve(self, result: BookResult) -> str:
        """Tap-time resolver: the REAL filename from archive.org/metadata
        (the {ia_id}.pdf guess 404s on many items)."""
        if not result.ia_id:
            return ""
        return await resolve_ia_pdf(result.ia_id)


async def resolve_ia_pdf(ia_id: str) -> str:
    """Ask archive.org/metadata for the item's real PDF filename.

    The guessed `{ia_id}.pdf` link is often wrong — the file may be named
    anything. Returns "" when the item has no PDF at all.
    """
    url = _METADATA.format(ia_id=ia_id)
    try:
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("metadata %s failed: %s: %s", ia_id, exc.__class__.__name__, exc)
        return ""

    files = data.get("files", []) or []
    pdfs = [f for f in files if str(f.get("name", "")).lower().endswith(".pdf")]
    if not pdfs:
        return ""
    # prefer the canonical "Text PDF" derivative, else the biggest/first
    def _rank(f: dict) -> int:
        fmt = str(f.get("format", ""))
        return 0 if "Text PDF" in fmt else 1

    best = sorted(pdfs, key=_rank)[0]
    name = quote(str(best["name"]))
    logger.info("Resolved IA %s → %s (%s)", ia_id, name[:70], best.get("format", "?"))
    return f"https://archive.org/download/{ia_id}/{name}"
