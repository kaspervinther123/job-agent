"""Job scrapers for Danish job sources."""

from .jobindex import scrape_jobindex
from .jobunivers import scrape_jobunivers

__all__ = ["scrape_jobindex", "scrape_jobunivers"]
