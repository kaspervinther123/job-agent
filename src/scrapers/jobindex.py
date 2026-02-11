"""Jobindex.dk scraper with specific filters."""

import asyncio
import logging
from datetime import datetime
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
    "konsulent",
    "samfundsvidenskabelig",
    "management konsulent",
]

# Location IDs for Jobindex
# Hovedstaden = 1, Midtjylland (Aarhus) = 3, Syddanmark (Odense) = 4
LOCATION_IDS = ["1", "3", "4"]


async def scrape_jobindex() -> list[Job]:
    """Scrape jobs from Jobindex.dk with filters for fuldtid positions."""
    jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for keyword in SEARCH_KEYWORDS:
            for location_id in LOCATION_IDS:
                try:
                    # Build URL with filters:
                    # - jobtypes=1 = Fuldtid
                    # - subid= location filter
                    search_url = (
                        f"https://www.jobindex.dk/jobsoegning?"
                        f"q={quote_plus(keyword)}"
                        f"&jobtypes=1"  # Fuldtid only
                        f"&subid={location_id}"
                    )

                    logger.info(f"Jobindex: Searching '{keyword}' in location {location_id}")
                    print(f"Jobindex: Searching '{keyword}' in location {location_id}")

                    await page.goto(search_url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(1)

                    # Parse page content
                    content = await page.content()
                    soup = BeautifulSoup(content, "html.parser")

                    # Find job listings - try multiple selectors
                    job_cards = soup.select("div.PaidJob, div.jobsearch-result, article.jix_robotjob")

                    if not job_cards:
                        # Try alternative selectors
                        job_cards = soup.select("[data-job-id], .jix-toolbar-top")

                    for card in job_cards:
                        try:
                            job = parse_job_card(card)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.warning(f"Failed to parse job card: {e}")
                            continue

                    print(f"Jobindex: Found {len(job_cards)} jobs for '{keyword}' in location {location_id}")

                    # Scrape page 2 as well
                    page2_url = f"{search_url}&page=2"
                    await page.goto(page2_url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(1)

                    content = await page.content()
                    soup = BeautifulSoup(content, "html.parser")
                    job_cards = soup.select("div.PaidJob, div.jobsearch-result, article.jix_robotjob, [data-job-id]")

                    for card in job_cards:
                        try:
                            job = parse_job_card(card)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            continue

                except Exception as e:
                    logger.error(f"Jobindex: Error scraping '{keyword}': {e}")
                    print(f"Jobindex: Error scraping '{keyword}': {e}")
                    continue

        await browser.close()

    # Remove duplicates
    seen_urls = set()
    unique_jobs = []
    for job in jobs:
        if job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)

    print(f"Jobindex: Total unique jobs found: {len(unique_jobs)}")
    return unique_jobs


def parse_job_card(card) -> Job | None:
    """Parse a job card element into a Job object."""
    try:
        # Title and URL - try multiple selectors
        title_elem = card.select_one(
            "a.PaidJob-inner, a.jobsearch-result__title, h4 a, "
            ".jix-toolbar-top__title a, a[data-click-event='job_click']"
        )
        if not title_elem:
            # Look for any link in the card
            title_elem = card.find("a", href=lambda x: x and "/jobannonce/" in x)

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if not title or len(title) < 5:
            return None

        url = title_elem.get("href", "")
        if url and not url.startswith("http"):
            url = f"https://www.jobindex.dk{url}"

        # Company
        company_elem = card.select_one(
            "p.PaidJob-company, span.jobsearch-result__company, "
            ".jix-toolbar-top__company, .jix_robotjob--company"
        )
        company = company_elem.get_text(strip=True) if company_elem else ""

        # Location
        location_elem = card.select_one(
            "p.PaidJob-location, span.jobsearch-result__location, "
            ".jix_robotjob--area, .jix-toolbar-top__location"
        )
        location = location_elem.get_text(strip=True) if location_elem else ""

        # Description (snippet)
        desc_elem = card.select_one(
            "p.PaidJob-excerpt, div.jobsearch-result__description, "
            ".PaidJob-desc, .jix_robotjob--text"
        )
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Deadline
        deadline_elem = card.select_one(
            ".jobsearch-result__date, .PaidJob-date, .jix_robotjob--deadline"
        )
        deadline = deadline_elem.get_text(strip=True) if deadline_elem else None

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
