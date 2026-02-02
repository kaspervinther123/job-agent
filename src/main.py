"""Main entry point for the Job Agent."""

import asyncio
import logging
import sys
from datetime import datetime

from .scrapers import JobindexScraper, JobnetScraper, CompanyPageScraper
from .agent import JobRelevanceAgent
from .storage import Database
from .email import EmailSender
from .config import settings, get_default_company_pages
from .utils import deduplicate_jobs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def scrape_jobs(db: Database) -> int:
    """Scrape jobs from all sources.

    Args:
        db: Database instance

    Returns:
        Number of new jobs added
    """
    all_jobs = []
    search_terms = ["konsulent", "analytiker", "fuldmægtig", "data", "policy"]

    # Scrape Jobindex
    logger.info("=== Scraping Jobindex ===")
    try:
        async with JobindexScraper() as scraper:
            async for job in scraper.scrape(search_terms, max_pages=2):
                all_jobs.append(job)
        logger.info(f"Found {len(all_jobs)} jobs from Jobindex")
    except Exception as e:
        logger.error(f"Jobindex scraping failed: {e}")

    # Scrape Jobnet
    jobnet_count = len(all_jobs)
    logger.info("=== Scraping Jobnet ===")
    try:
        async with JobnetScraper() as scraper:
            async for job in scraper.scrape(search_terms, max_pages=2):
                all_jobs.append(job)
        logger.info(f"Found {len(all_jobs) - jobnet_count} jobs from Jobnet")
    except Exception as e:
        logger.error(f"Jobnet scraping failed: {e}")

    # Scrape company career pages
    company_count = len(all_jobs)
    logger.info("=== Scraping Company Career Pages ===")
    try:
        company_sources = get_default_company_pages()
        async with CompanyPageScraper() as scraper:
            async for job in scraper.scrape(company_sources=company_sources):
                all_jobs.append(job)
        logger.info(f"Found {len(all_jobs) - company_count} jobs from company pages")
    except Exception as e:
        logger.error(f"Company page scraping failed: {e}")

    # Deduplicate
    unique_jobs = deduplicate_jobs(all_jobs)
    logger.info(f"Total unique jobs: {len(unique_jobs)} (from {len(all_jobs)} scraped)")

    # Insert new jobs into database
    new_count = 0
    for job in unique_jobs:
        if db.insert_job(job):
            new_count += 1

    logger.info(f"Added {new_count} new jobs to database")
    return new_count


async def analyze_jobs(db: Database) -> int:
    """Analyze unanalyzed jobs with Claude.

    Args:
        db: Database instance

    Returns:
        Number of jobs analyzed
    """
    # Get unanalyzed jobs
    unanalyzed = db.get_unanalyzed_jobs(limit=50)
    if not unanalyzed:
        logger.info("No jobs to analyze")
        return 0

    logger.info(f"=== Analyzing {len(unanalyzed)} jobs with Claude ===")

    # Get feedback history for context
    liked_jobs = db.get_liked_jobs(limit=5)
    disliked_jobs = db.get_disliked_jobs(limit=5)

    # Analyze with Claude
    agent = JobRelevanceAgent()
    results = await agent.analyze_jobs_batch(unanalyzed, liked_jobs, disliked_jobs)

    # Update database with results
    for job, analysis in results:
        db.update_job_analysis(
            job_hash=job.job_hash,
            relevance_score=analysis["score"],
            relevance_reasoning=analysis["reasoning"],
            concerns=analysis["concerns"],
            highlights=analysis["highlights"],
        )

    logger.info(f"Analyzed {len(results)} jobs")
    return len(results)


def send_digest(db: Database, min_relevance: int = 60) -> bool:
    """Send email digest of relevant jobs.

    Args:
        db: Database instance
        min_relevance: Minimum relevance score to include

    Returns:
        True if sent successfully
    """
    # Get relevant jobs that haven't been emailed
    jobs = db.get_jobs_for_email(min_relevance=min_relevance)

    if not jobs:
        logger.info("No new relevant jobs to send")
        return True

    logger.info(f"=== Sending digest with {len(jobs)} jobs ===")

    # Send email
    sender = EmailSender()
    success = sender.send_digest(jobs)

    if success:
        # Mark jobs as emailed
        job_hashes = [job.job_hash for job in jobs]
        db.mark_jobs_emailed(job_hashes)
        logger.info(f"Marked {len(job_hashes)} jobs as emailed")

    return success


async def run_pipeline():
    """Run the complete job agent pipeline."""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Job Agent starting at {start_time.isoformat()}")
    logger.info("=" * 60)

    # Initialize database
    db = Database(settings.db_path)

    # Print stats
    stats = db.get_stats()
    logger.info(f"Database stats: {stats}")

    try:
        # Step 1: Scrape new jobs
        new_jobs = await scrape_jobs(db)
        logger.info(f"Step 1 complete: {new_jobs} new jobs scraped")

        # Step 2: Analyze with Claude
        analyzed = await analyze_jobs(db)
        logger.info(f"Step 2 complete: {analyzed} jobs analyzed")

        # Step 3: Send email digest
        sent = send_digest(db)
        logger.info(f"Step 3 complete: Email sent = {sent}")

        # Final stats
        final_stats = db.get_stats()
        logger.info(f"Final database stats: {final_stats}")

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        raise

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info(f"Job Agent completed in {duration:.1f} seconds")
    logger.info("=" * 60)


def main():
    """Entry point."""
    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()
