"""
JobUnivers.dk scraper - Djøf's job board for professionals
Uses Playwright because the site is JavaScript-rendered.
"""
import asyncio
import logging
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from ..models.job import Job

logger = logging.getLogger(__name__)

# Maximum pages to scrape (safety limit)
MAX_PAGES = 20


async def scrape_jobunivers() -> list[Job]:
    """Scrape jobs from JobUnivers.dk (Djøf's job board)."""
    jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Start at the main job listing page
            base_url = "https://www.jobunivers.dk/job/"
            print(f"JobUnivers: Loading {base_url}")

            await page.goto(base_url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)  # Wait for JavaScript to render

            page_num = 1
            offset = 0

            while page_num <= MAX_PAGES:
                print(f"JobUnivers: Scraping page {page_num} (offset {offset})")

                # Get page content
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")

                # Find all job links - they have pattern /job/?job=NUMBER
                job_links = soup.find_all("a", href=lambda x: x and "/job/?job=" in x)

                if not job_links:
                    print(f"JobUnivers: No more jobs found on page {page_num}")
                    break

                # Extract unique job URLs from this page
                seen_on_page = set()
                jobs_on_page = 0

                for link in job_links:
                    href = link.get("href", "")
                    if not href or href in seen_on_page:
                        continue
                    seen_on_page.add(href)

                    # Build full URL
                    if href.startswith("/"):
                        job_url = f"https://www.jobunivers.dk{href}"
                    else:
                        job_url = href

                    # Get title from link text
                    title = link.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    # Try to find parent container for more info
                    parent = link.find_parent(["div", "article", "li", "tr"])

                    company = ""
                    location = ""
                    deadline = ""

                    if parent:
                        # Look for company name
                        company_elem = parent.find(
                            ["span", "div", "td"],
                            class_=lambda x: x and any(c in str(x).lower() for c in ["company", "virksomhed", "employer"])
                        )
                        if company_elem:
                            company = company_elem.get_text(strip=True)

                        # Try to get all text and parse it
                        parent_text = parent.get_text(" | ", strip=True)

                        # Often the structure is: Title | Company | Location | Deadline
                        parts = [p.strip() for p in parent_text.split("|") if p.strip()]
                        if len(parts) >= 2 and not company:
                            # Second part is often company
                            company = parts[1] if parts[1] != title else ""
                        if len(parts) >= 3:
                            location = parts[2] if "deadline" not in parts[2].lower() else ""
                        if len(parts) >= 4:
                            deadline = parts[-1] if any(c.isdigit() for c in parts[-1]) else ""

                    job = Job(
                        title=title,
                        company=company,
                        location=location,
                        description="",  # Would need to visit each job page for full description
                        url=job_url,
                        source="jobunivers",
                        deadline=deadline,
                        scraped_at=datetime.now(),
                    )
                    jobs.append(job)
                    jobs_on_page += 1

                print(f"JobUnivers: Found {jobs_on_page} jobs on page {page_num}")

                if jobs_on_page == 0:
                    break

                # Try to go to next page
                # JobUnivers uses offset-based pagination
                offset += 10
                next_url = f"{base_url}?offset={offset}"

                try:
                    await page.goto(next_url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(1)
                    page_num += 1
                except Exception as e:
                    print(f"JobUnivers: Error navigating to page {page_num + 1}: {e}")
                    break

        except Exception as e:
            logger.error(f"JobUnivers: Error during scraping: {e}")
            print(f"JobUnivers: Error during scraping: {e}")

        finally:
            await browser.close()

    # Remove duplicates based on URL
    seen_urls = set()
    unique_jobs = []
    for job in jobs:
        # Normalize URL (remove offset parameter for dedup)
        clean_url = job.url.split("&offset=")[0]
        if clean_url not in seen_urls:
            seen_urls.add(clean_url)
            unique_jobs.append(job)

    print(f"JobUnivers: Total unique jobs found: {len(unique_jobs)}")
    return unique_jobs
