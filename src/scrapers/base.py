"""Base scraper class."""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..models.job import Job


class BaseScraper(ABC):
    """Abstract base class for job scrapers."""

    name: str = "base"

    @abstractmethod
    async def scrape(self, search_terms: list[str], **kwargs) -> AsyncIterator[Job]:
        """Scrape jobs matching the search terms.

        Args:
            search_terms: List of search terms to look for
            **kwargs: Additional scraper-specific parameters

        Yields:
            Job objects
        """
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
