"""Jobindex.dk scraper with specific filters."""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from ..models.job import Job

logger = logging.getLogger(__name__)

# Search configuration
SEARCH_KEYWORDS = [
    "statskundskab",
    "cand.scient.pol",
    "ac fuldmægtig",
    "akademisk fuldmægtig",
    "analysekonsulent",
    "samfundsvidenskabelig",
]

# Location IDs for Jobindex
# Hovedstaden = 1, Midtjylland (Aarhus) = 3, Syddanmark (Odense) = 4
LOCATION_IDS = ["1", "3", "4"]

# Maximum pages to scrape per search (safety limit)
MAX_PAGES = 10


async def scrape_jobindex() -> list[Job]:
    """Scrape jobs from Jobindex.dk with filters for fuldtid positions."""
    jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for keyword in SEARCH_KEYWORDS:
            for location_id in LOCATION_IDS:
                try:
                    page_num = 1
                    has_more_pages = True

                    while has_more_pages and page_num <= MAX_PAGES:
                        # Build URL with filters
                        search_url = (
                            f"https://www.jobindex.dk/jobsoegning?"
                            f"q={quote_plus(keyword)}"
                            f"&jobtypes=1"  # Fuldtid only
                            f"&subid={location_id}"
                        )
                        if page_num > 1:
                            search_url += f"&page={page_num}"

                        print(f"Jobindex: Searching '{keyword}' in location {location_id}, page {page_num}")

                        await page.goto(search_url, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(1)

                        # Parse page content
                        content = await page.content()
                        soup = BeautifulSoup(content, "html.parser")

                        # Find job listings using multiple selectors
                        job_cards = soup.select("div.PaidJob, div.jobsearch-result, article.jix_robotjob")

                        # Also try finding job wrappers by ID pattern
                        if not job_cards:
                            job_cards = soup.select("[id^='jobad-wrapper-']")

                        if not job_cards:
                            print(f"Jobindex: No jobs found on page {page_num}, stopping pagination")
                            has_more_pages = False
                            continue

                        jobs_on_page = 0
                        for card in job_cards:
                            try:
                                job = parse_job_card(card)
                                if job:
                                    jobs.append(job)
                                    jobs_on_page += 1
                            except Exception as e:
                                logger.warning(f"Failed to parse job card: {e}")
                                continue

                        print(f"Jobindex: Found {jobs_on_page} jobs on page {page_num}")

                        # Check if there are more pages
                        # Look for pagination info or next page link
                        next_page = soup.select_one("a.page-link[rel='next'], a[aria-label='Næste']")
                        if not next_page and jobs_on_page < 20:
                            # Less than full page = last page
                            has_more_pages = False
                        else:
                            page_num += 1

                except Exception as e:
                    logger.error(f"Jobindex: Error scraping '{keyword}': {e}")
                    print(f"Jobindex: Error scraping '{keyword}': {e}")
                    continue

        await browser.close()

    # Remove duplicates based on URL
    seen_urls = set()
    unique_jobs = []
    for job in jobs:
        if job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)

    print(f"Jobindex: Total unique jobs found: {len(unique_jobs)}")
    return unique_jobs


def parse_job_card(card) -> Optional[Job]:
    """Parse a job card element into a Job object."""
    try:
        # Title - look for h4 > a or other title patterns
        title_elem = card.select_one("h4 a, a.PaidJob-inner, .jix-toolbar-top__title a")

        if not title_elem:
            # Try finding any link to a job page
            title_elem = card.find("a", href=lambda x: x and ("/jobannonce/" in x or "candidate.hr-manager" in x))

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if not title or len(title) < 5:
            return None

        # URL
        url = title_elem.get("href", "")
        if url and not url.startswith("http"):
            url = f"https://www.jobindex.dk{url}"

        # Company - try multiple selectors
        company_elem = card.select_one(
            ".jix-toolbar-top__company a, "
            "p.PaidJob-company, "
            ".jix_robotjob--company, "
            "a[href*='/telefonbog/']"
        )
        company = company_elem.get_text(strip=True) if company_elem else ""

        # Location
        location_elem = card.select_one(
            "span.jix_robotjob--area, "
            ".jobad-element-area span, "
            "p.PaidJob-location"
        )
        location = location_elem.get_text(strip=True) if location_elem else ""

        # Description (snippet from the card)
        desc_elem = card.select_one(
            ".PaidJob-inner p, "
            ".jix_robotjob--text, "
            ".jobsearch-result__description"
        )
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Deadline/date
        deadline = None
        time_elem = card.select_one("time[datetime]")
        if time_elem:
            deadline = time_elem.get("datetime") or time_elem.get_text(strip=True)
        else:
            date_elem = card.select_one(".jix-toolbar__pubdate, .PaidJob-date")
            if date_elem:
                deadline = date_elem.get_text(strip=True)

        return Job(
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            source="jobindex",
            deadline=deadline,
            scraped_at=datetime.now(),
        )

    except Exception as e:
        logger.warning(f"Error parsing job card: {e}")
        return None
