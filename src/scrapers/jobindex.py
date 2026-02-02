"""Jobindex.dk scraper."""

import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page

from .base import BaseScraper
from ..models.job import Job, JobSource
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class JobindexScraper(BaseScraper):
    """Scraper for Jobindex.dk."""

    name = "jobindex"
    BASE_URL = "https://www.jobindex.dk"

    def __init__(self, rate_limit: float = 0.5):
        """Initialize the scraper.

        Args:
            rate_limit: Requests per second
        """
        self.rate_limiter = RateLimiter(rate_limit)
        self._browser: Browser | None = None
        self._playwright = None

    async def __aenter__(self):
        """Start browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def scrape(
        self,
        search_terms: list[str],
        location: str = "Danmark",
        max_pages: int = 3,
        **kwargs,
    ) -> AsyncIterator[Job]:
        """Scrape jobs from Jobindex.

        Args:
            search_terms: Terms to search for
            location: Location filter
            max_pages: Maximum pages to scrape per search term

        Yields:
            Job objects
        """
        if not self._browser:
            raise RuntimeError("Scraper must be used as async context manager")

        page = await self._browser.new_page()

        try:
            for term in search_terms:
                logger.info(f"Searching Jobindex for: {term}")

                for page_num in range(1, max_pages + 1):
                    await self.rate_limiter.wait()

                    # Build search URL
                    search_url = (
                        f"{self.BASE_URL}/jobsoegning?"
                        f"q={quote_plus(term)}"
                        f"&page={page_num}"
                    )

                    try:
                        await page.goto(search_url, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(1)  # Wait for dynamic content

                        # Get page content
                        content = await page.content()
                        soup = BeautifulSoup(content, "html.parser")

                        # Find job listings
                        job_cards = soup.select("div.PaidJob, div.jobsearch-result")

                        if not job_cards:
                            logger.debug(f"No more jobs found on page {page_num}")
                            break

                        for card in job_cards:
                            try:
                                job = self._parse_job_card(card)
                                if job:
                                    yield job
                            except Exception as e:
                                logger.warning(f"Failed to parse job card: {e}")
                                continue

                    except Exception as e:
                        logger.error(f"Failed to scrape page {page_num} for '{term}': {e}")
                        break

        finally:
            await page.close()

    def _parse_job_card(self, card) -> Job | None:
        """Parse a job card element into a Job object."""
        try:
            # Title and URL
            title_elem = card.select_one("a.PaidJob-inner, a.jobsearch-result__title, h4 a")
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            url = title_elem.get("href", "")
            if url and not url.startswith("http"):
                url = f"{self.BASE_URL}{url}"

            # Company
            company_elem = card.select_one(
                "p.PaidJob-company, span.jobsearch-result__company, .jix-toolbar-top__company"
            )
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Location
            location_elem = card.select_one(
                "p.PaidJob-location, span.jobsearch-result__location, .jix_robotjob--area"
            )
            location = location_elem.get_text(strip=True) if location_elem else "Danmark"

            # Description (snippet)
            desc_elem = card.select_one(
                "p.PaidJob-excerpt, div.jobsearch-result__description, .PaidJob-desc"
            )
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Posted date (if available)
            date_elem = card.select_one(".jobsearch-result__date, .PaidJob-date")
            posted_date = None
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # Parse Danish date formats like "i dag", "i går", "3 dage siden"
                posted_date = self._parse_danish_date(date_text)

            return Job(
                title=title,
                company=company,
                location=location,
                description=description,
                url=url,
                source=JobSource.JOBINDEX,
                posted_date=posted_date,
            )

        except Exception as e:
            logger.warning(f"Error parsing job card: {e}")
            return None

    def _parse_danish_date(self, date_text: str) -> datetime | None:
        """Parse Danish relative date strings."""
        date_text = date_text.lower().strip()

        if "i dag" in date_text:
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif "i går" in date_text:
            from datetime import timedelta
            return (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif "dage siden" in date_text:
            try:
                from datetime import timedelta
                days = int(date_text.split()[0])
                return (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
            except (ValueError, IndexError):
                pass

        return None
