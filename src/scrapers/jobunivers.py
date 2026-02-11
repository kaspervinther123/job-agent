"""
JobUnivers.dk scraper - Djøf's job board for professionals
"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import re
from ..models.job import Job


async def scrape_jobunivers() -> list[Job]:
    """Scrape jobs from JobUnivers.dk with filters"""
    jobs = []

    # Search keywords relevant to the profile
    keywords = [
        "konsulent",
        "analysekonsulent",
        "fuldmægtig",
        "samfund",
    ]

    # Locations to search
    locations = ["Hovedstaden", "Midtjylland", "Syddanmark"]  # Covers Copenhagen, Aarhus, Odense

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for keyword in keywords:
            for location in locations:
                try:
                    # JobUnivers search URL pattern
                    url = f"https://www.jobunivers.dk/job/?LedigStilling={keyword}&LedigStillingLokation={location}"

                    response = await client.get(url, headers=headers)
                    if response.status_code != 200:
                        print(f"JobUnivers: Failed to fetch {url}: {response.status_code}")
                        continue

                    soup = BeautifulSoup(response.text, "html.parser")

                    # Find job listings
                    job_cards = soup.select("div.LedigStilling, article.job-listing, div.job-item")

                    # Also try finding links that look like job listings
                    if not job_cards:
                        job_links = soup.find_all("a", href=re.compile(r"/job/\?job=\d+"))
                        for link in job_links:
                            parent = link.find_parent(["div", "article", "li"])
                            if parent and parent not in job_cards:
                                job_cards.append(parent)

                    for card in job_cards:
                        try:
                            # Extract title
                            title_elem = card.find(["h2", "h3", "a"], class_=re.compile(r"title|heading", re.I))
                            if not title_elem:
                                title_elem = card.find("a", href=re.compile(r"/job/\?job="))

                            if not title_elem:
                                continue

                            title = title_elem.get_text(strip=True)
                            if not title or len(title) < 5:
                                continue

                            # Extract URL
                            link = card.find("a", href=re.compile(r"/job/"))
                            if link and link.get("href"):
                                href = link["href"]
                                if href.startswith("/"):
                                    job_url = f"https://www.jobunivers.dk{href}"
                                else:
                                    job_url = href
                            else:
                                continue

                            # Extract company
                            company = ""
                            company_elem = card.find(class_=re.compile(r"company|employer|virksomhed", re.I))
                            if company_elem:
                                company = company_elem.get_text(strip=True)

                            # Extract location
                            job_location = location
                            loc_elem = card.find(class_=re.compile(r"location|lokation|sted", re.I))
                            if loc_elem:
                                job_location = loc_elem.get_text(strip=True)

                            # Extract deadline
                            deadline = None
                            deadline_elem = card.find(class_=re.compile(r"deadline|date|dato", re.I))
                            if deadline_elem:
                                deadline = deadline_elem.get_text(strip=True)

                            # Get full description from job page
                            description = ""
                            try:
                                job_response = await client.get(job_url, headers=headers)
                                if job_response.status_code == 200:
                                    job_soup = BeautifulSoup(job_response.text, "html.parser")
                                    desc_elem = job_soup.find(class_=re.compile(r"description|content|text|body", re.I))
                                    if desc_elem:
                                        description = desc_elem.get_text(strip=True)[:2000]
                            except Exception:
                                pass

                            job = Job(
                                title=title,
                                company=company,
                                location=job_location,
                                description=description,
                                url=job_url,
                                source="jobunivers",
                                deadline=deadline,
                                scraped_at=datetime.now(),
                            )
                            jobs.append(job)

                        except Exception as e:
                            print(f"JobUnivers: Error parsing job card: {e}")
                            continue

                    print(f"JobUnivers: Found {len(job_cards)} jobs for '{keyword}' in {location}")

                except Exception as e:
                    print(f"JobUnivers: Error fetching {keyword} in {location}: {e}")
                    continue

    # Remove duplicates based on URL
    seen_urls = set()
    unique_jobs = []
    for job in jobs:
        if job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)

    print(f"JobUnivers: Total unique jobs found: {len(unique_jobs)}")
    return unique_jobs
