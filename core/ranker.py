"""Merge, dedupe and rank results coming from all sources."""
from rapidfuzz import fuzz

from core.models import BookResult
from utils.text import normalize_query


def _dedupe_key(r: BookResult) -> str:
    if r.ia_id:
        return f"ia:{r.ia_id}"                      # same IA scan = same book
    return "t:" + normalize_query(f"{r.title} {r.author}")[:60]


def _score(r: BookResult, query_n: str) -> float:
    score = fuzz.token_set_ratio(normalize_query(r.title), query_n)
    if r.pdf_url:
        score += 20                                  # immediately downloadable wins ties
    if r.detail.get("public_domain"):
        score += 8
    if r.year:
        score += 3
    return score


def rank_results(query: str, results: list[BookResult], limit: int = 5) -> list[BookResult]:
    """Dedupe across sources, merge complementary info, sort best-first."""
    query_n = normalize_query(query)
    best: dict[str, BookResult] = {}

    for r in results:
        key = _dedupe_key(r)
        prior = best.get(key)
        if prior is None:
            best[key] = r
            continue
        # same book from two sources → merge the useful bits
        if r.pdf_url and not prior.pdf_url:
            prior.pdf_url = r.pdf_url
        if r.year and not prior.year:
            prior.year = r.year
        if r.page_url and not prior.page_url:
            prior.page_url = r.page_url
        if len(r.title) > len(prior.title):          # keep the richer title
            prior.title = r.title
        if r.author != "—" and prior.author == "—":
            prior.author = r.author
        best[key] = prior

    ranked = sorted(best.values(), key=lambda r: _score(r, query_n), reverse=True)
    return ranked[:limit]
