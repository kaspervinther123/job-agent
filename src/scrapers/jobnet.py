"""Jobnet.dk scraper for public sector jobs."""

import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser

from .base import BaseScraper
from ..models.job import Job, JobSource
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class JobnetScraper(BaseScraper):
    """Scraper for Jobnet.dk (Danish public job portal)."""

    name = "jobnet"
    BASE_URL = "https://job.jobnet.dk"

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
        max_pages: int = 3,
        **kwargs,
    ) -> AsyncIterator[Job]:
        """Scrape jobs from Jobnet.

        Args:
            search_terms: Terms to search for
            max_pages: Maximum pages to scrape per search term

        Yields:
            Job objects
        """
        if not self._browser:
            raise RuntimeError("Scraper must be used as async context manager")

        page = await self._browser.new_page()

        try:
            for term in search_terms:
                logger.info(f"Searching Jobnet for: {term}")

                for page_num in range(1, max_pages + 1):
                    await self.rate_limiter.wait()

                    # Build search URL
                    # Jobnet uses a different URL structure
                    search_url = (
                        f"{self.BASE_URL}/CV/FindWork/SearchResult.aspx?"
                        f"SearchString={quote_plus(term)}"
                        f"&Page={page_num}"
                    )

                    try:
                        await page.goto(search_url, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(2)  # Wait for dynamic content

                        content = await page.content()
                        soup = BeautifulSoup(content, "html.parser")

                        # Find job listings - Jobnet uses specific CSS classes
                        job_cards = soup.select(
                            "div.job-item, article.job-card, div.search-result-item, tr.result-row"
                        )

                        if not job_cards:
                            # Try alternative selector
                            job_cards = soup.select("div[class*='job'], div[class*='result']")

                        if not job_cards:
                            logger.debug(f"No jobs found on page {page_num}")
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
            title_elem = card.select_one("a[href*='job'], h2 a, h3 a, .job-title a")
            if not title_elem:
                # Try finding any link
                title_elem = card.select_one("a")

            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            url = title_elem.get("href", "")
            if url and not url.startswith("http"):
                url = f"{self.BASE_URL}{url}"

            # Company/Employer
            company_elem = card.select_one(
                ".company, .employer, .job-company, [class*='company'], [class*='employer']"
            )
            company = company_elem.get_text(strip=True) if company_elem else "Offentlig arbejdsgiver"

            # Location
            location_elem = card.select_one(
                ".location, .job-location, [class*='location'], [class*='area']"
            )
            location = location_elem.get_text(strip=True) if location_elem else "Danmark"

            # Description
            desc_elem = card.select_one(
                ".description, .job-description, .excerpt, p"
            )
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Deadline
            deadline_elem = card.select_one(
                ".deadline, .job-deadline, [class*='deadline'], [class*='date']"
            )
            deadline = None
            if deadline_elem:
                deadline = self._parse_danish_date(deadline_elem.get_text(strip=True))

            return Job(
                title=title,
                company=company,
                location=location,
                description=description,
                url=url,
                source=JobSource.JOBNET,
                sector="offentlig",  # Jobnet is primarily public sector
                deadline=deadline,
            )

        except Exception as e:
            logger.warning(f"Error parsing Jobnet job card: {e}")
            return None

    def _parse_danish_date(self, date_text: str) -> datetime | None:
        """Parse Danish date strings."""
        import re

        date_text = date_text.lower().strip()

        # Try to find date pattern like "15. januar 2026" or "15-01-2026"
        danish_months = {
            "januar": 1, "februar": 2, "marts": 3, "april": 4,
            "maj": 5, "juni": 6, "juli": 7, "august": 8,
            "september": 9, "oktober": 10, "november": 11, "december": 12,
        }

        # Pattern: "15. januar 2026"
        match = re.search(r"(\d{1,2})\.\s*(\w+)\s*(\d{4})", date_text)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            if month_name in danish_months:
                return datetime(year, danish_months[month_name], day)

        # Pattern: "15-01-2026" or "15/01/2026"
        match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", date_text)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            try:
                return datetime(year, month, day)
            except ValueError:
                pass

        return None
