"""Contract every book source must follow."""
from abc import ABC, abstractmethod

from core.models import BookResult


class BookSource(ABC):
    name: str = "source"

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[BookResult]:
        """Return up to `limit` results, best first. Return [] on nothing found."""

    async def resolve(self, result: BookResult) -> str:
        """Best-effort direct PDF URL for a search result, called at tap time.
        Default: nothing extra beyond result.pdf_url. Sources that can look up
        a better link (IA metadata, Gutenberg patterns, …) override this."""
        return ""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.name}'>"
