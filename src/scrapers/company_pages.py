"""Generic company career page scraper."""

import asyncio
import logging
from typing import AsyncIterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser

from .base import BaseScraper
from ..models.job import Job, JobSource
from ..config import CompanySource
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class CompanyPageScraper(BaseScraper):
    """Generic scraper for company career pages."""

    name = "company_pages"

    def __init__(self, rate_limit: float = 0.3):
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
        search_terms: list[str] = None,  # Not used for company pages
        company_sources: list[CompanySource] = None,
        **kwargs,
    ) -> AsyncIterator[Job]:
        """Scrape jobs from company career pages.

        Args:
            search_terms: Ignored for company pages
            company_sources: List of company career pages to scrape

        Yields:
            Job objects
        """
        if not self._browser:
            raise RuntimeError("Scraper must be used as async context manager")

        if not company_sources:
            return

        page = await self._browser.new_page()

        try:
            for source in company_sources:
                await self.rate_limiter.wait()
                logger.info(f"Scraping career page: {source.name}")

                try:
                    await page.goto(source.url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(2)  # Wait for dynamic content

                    content = await page.content()
                    soup = BeautifulSoup(content, "html.parser")

                    # Try to find job listings using common patterns
                    jobs = await self._extract_jobs(soup, source)

                    for job in jobs:
                        yield job

                except Exception as e:
                    logger.error(f"Failed to scrape {source.name}: {e}")
                    continue

        finally:
            await page.close()

    async def _extract_jobs(self, soup: BeautifulSoup, source: CompanySource) -> list[Job]:
        """Extract jobs from a career page using heuristics.

        This uses multiple strategies to find job listings since
        career pages vary widely in structure.
        """
        jobs = []

        # Strategy 1: Look for common job listing containers
        job_selectors = [
            # Generic job listing selectors
            "div[class*='job']",
            "article[class*='job']",
            "li[class*='job']",
            "div[class*='position']",
            "div[class*='vacancy']",
            "div[class*='career']",
            "div[class*='opening']",
            # Table-based listings
            "tr[class*='job']",
            # Card-based listings
            "div[class*='card']",
            # Link lists
            "a[href*='job']",
            "a[href*='career']",
            "a[href*='position']",
            "a[href*='stilling']",  # Danish for position
            "a[href*='ledige']",  # Danish for vacancies
        ]

        for selector in job_selectors:
            elements = soup.select(selector)
            if elements and len(elements) >= 1:
                for elem in elements[:20]:  # Limit to 20 jobs per page
                    job = self._parse_job_element(elem, source)
                    if job:
                        jobs.append(job)
                break  # Use first successful selector

        # Strategy 2: If no jobs found, look for any links that look like job postings
        if not jobs:
            links = soup.find_all("a", href=True)
            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Check if this looks like a job link
                if (
                    len(text) > 10
                    and len(text) < 200
                    and not any(skip in text.lower() for skip in ["login", "sign", "cookie", "privacy", "contact"])
                    and any(kw in href.lower() for kw in ["job", "career", "position", "stilling", "ledige", "vacancy"])
                ):
                    url = href if href.startswith("http") else urljoin(source.url, href)
                    jobs.append(
                        Job(
                            title=text,
                            company=source.name,
                            location="Danmark",
                            description="",  # Would need to follow link to get description
                            url=url,
                            source=JobSource.COMPANY_PAGE,
                            sector=source.sector,
                        )
                    )

        return jobs

    def _parse_job_element(self, elem, source: CompanySource) -> Job | None:
        """Parse a job element into a Job object."""
        try:
            # Find title - usually in a heading or link
            title_elem = elem.select_one("h1, h2, h3, h4, a[href]")
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 5:
                return None

            # Skip navigation/footer links
            skip_words = [
                "login", "sign", "cookie", "privacy", "contact", "about",
                "home", "menu", "nav", "footer", "header", "search"
            ]
            if any(word in title.lower() for word in skip_words):
                return None

            # Get URL
            link_elem = elem.select_one("a[href]") or title_elem
            url = ""
            if link_elem and link_elem.name == "a":
                url = link_elem.get("href", "")
                if url and not url.startswith("http"):
                    url = urljoin(source.url, url)

            # Try to find location
            location_elem = elem.select_one(
                "[class*='location'], [class*='place'], [class*='area']"
            )
            location = location_elem.get_text(strip=True) if location_elem else "Danmark"

            # Try to find description/excerpt
            desc_elem = elem.select_one(
                "[class*='description'], [class*='excerpt'], [class*='summary'], p"
            )
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            return Job(
                title=title,
                company=source.name,
                location=location,
                description=description[:500],  # Limit description length
                url=url or source.url,
                source=JobSource.COMPANY_PAGE,
                sector=source.sector,
            )

        except Exception as e:
            logger.warning(f"Error parsing job element: {e}")
            return None
