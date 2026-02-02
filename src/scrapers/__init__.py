"""Job scrapers for various Danish job sources."""

from .base import BaseScraper
from .jobindex import JobindexScraper
from .jobnet import JobnetScraper
from .company_pages import CompanyPageScraper

__all__ = ["BaseScraper", "JobindexScraper", "JobnetScraper", "CompanyPageScraper"]
