"""Source registry — every source the bot searches (run in parallel by the handler)."""
from sources.base import BookSource
from sources.googlebooks import GoogleBooksSource
from sources.gutenberg import GutenbergSource
from sources.internetarchive import InternetArchiveSource
from sources.openlibrary import OpenLibrarySource

REGISTRY: list[BookSource] = [
    OpenLibrarySource(),
    InternetArchiveSource(),
    GoogleBooksSource(),
    GutenbergSource(),
]
