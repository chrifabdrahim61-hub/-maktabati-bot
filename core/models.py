"""Data model shared by all sources and (later) the ranking step."""
from dataclasses import dataclass, field


@dataclass
class BookResult:
    title: str
    author: str = ""
    year: int | str = ""
    source: str = ""            # display name, e.g. "Open Library"
    lang: str = ""              # book language if the source reports it

    # direct-download info (filled when the source can resolve a PDF right now)
    pdf_url: str = ""

    # provider-specific ids used in Step 5 to resolve PDFs
    openlibrary_id: str = ""    # e.g. OL12345W
    ia_id: str = ""             # Internet Archive identifier
    gutenberg_id: int = 0

    # human-readable page — transparency for the user
    page_url: str = ""

    # any extra source-specific data (ebook_access, formats, …)
    detail: dict = field(default_factory=dict)
