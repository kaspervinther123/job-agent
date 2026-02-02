"""Job deduplication utilities."""

import hashlib

from ..models.job import Job


def compute_job_hash(title: str, company: str, location: str) -> str:
    """Compute a unique hash for a job based on title, company, and location.

    Args:
        title: Job title
        company: Company name
        location: Job location

    Returns:
        16-character hash string
    """
    normalized = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def deduplicate_jobs(jobs: list[Job]) -> list[Job]:
    """Remove duplicate jobs from a list.

    Args:
        jobs: List of jobs to deduplicate

    Returns:
        List of unique jobs (first occurrence kept)
    """
    seen_hashes: set[str] = set()
    unique_jobs: list[Job] = []

    for job in jobs:
        if job.job_hash not in seen_hashes:
            seen_hashes.add(job.job_hash)
            unique_jobs.append(job)

    return unique_jobs
