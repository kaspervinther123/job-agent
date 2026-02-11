"""SQLite database for storing jobs and feedback."""

import sqlite3
from pathlib import Path
from typing import Optional

from ..models.job import Job
from ..models.feedback import Feedback, FeedbackType


class Database:
    """SQLite database for job agent."""

    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_hash TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    description TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    sector TEXT,
                    posted_date TEXT,
                    deadline TEXT,
                    salary TEXT,
                    relevance_score INTEGER,
                    relevance_reasoning TEXT,
                    concerns TEXT,
                    highlights TEXT,
                    scraped_at TEXT NOT NULL,
                    emailed_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_hash TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_hash) REFERENCES jobs(job_hash)
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
                CREATE INDEX IF NOT EXISTS idx_jobs_relevance ON jobs(relevance_score);
                CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at);
                CREATE INDEX IF NOT EXISTS idx_feedback_job ON feedback(job_hash);
            """)

    def job_exists(self, job_hash: str) -> bool:
        """Check if a job already exists in the database."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM jobs WHERE job_hash = ?", (job_hash,)
            )
            return cursor.fetchone() is not None

    def insert_job(self, job: Job) -> bool:
        """Insert a new job. Returns True if inserted, False if already exists."""
        if self.job_exists(job.job_hash):
            return False

        with self._get_connection() as conn:
            data = job.to_db_dict()
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            conn.execute(
                f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",
                tuple(data.values()),
            )
        return True

    def update_job_analysis(
        self,
        job_hash: str,
        relevance_score: int,
        relevance_reasoning: str,
        concerns: list[str],
        highlights: list[str],
    ) -> None:
        """Update job with Claude's analysis."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET relevance_score = ?,
                    relevance_reasoning = ?,
                    concerns = ?,
                    highlights = ?
                WHERE job_hash = ?
                """,
                (
                    relevance_score,
                    relevance_reasoning,
                    ",".join(concerns) if concerns else None,
                    ",".join(highlights) if highlights else None,
                    job_hash,
                ),
            )

    def get_unanalyzed_jobs(self, limit: int = 50) -> list[Job]:
        """Get jobs that haven't been analyzed by Claude yet."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM jobs
                WHERE relevance_score IS NULL
                ORDER BY scraped_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [Job.from_db_row(dict(row)) for row in cursor.fetchall()]

    def get_jobs_for_email(self, min_relevance: int = 60) -> list[Job]:
        """Get relevant jobs that haven't been emailed yet.

        Includes jobs that either:
        1. Have relevance_score >= min_relevance, OR
        2. Contain key keywords (cand.scient.pol, statskundskab, ac-fuldmægtig, akademisk fuldmægtig)
           in title or description, regardless of AI score
        """
        # Keywords that should always be included
        must_include_keywords = [
            "cand.scient.pol",
            "statskundskab",
            "ac-fuldmægtig",
            "akademisk fuldmægtig",
            "ac fuldmægtig",
        ]

        with self._get_connection() as conn:
            # Build keyword conditions for SQL
            keyword_conditions = " OR ".join([
                "(LOWER(title) LIKE ? OR LOWER(description) LIKE ?)"
                for _ in must_include_keywords
            ])

            # Parameters: first min_relevance, then pairs of keyword patterns
            params = [min_relevance]
            for kw in must_include_keywords:
                pattern = f"%{kw.lower()}%"
                params.extend([pattern, pattern])

            cursor = conn.execute(
                f"""
                SELECT * FROM jobs
                WHERE emailed_at IS NULL
                  AND relevance_score IS NOT NULL
                  AND (
                      relevance_score >= ?
                      OR ({keyword_conditions})
                  )
                ORDER BY relevance_score DESC, scraped_at DESC
                """,
                params,
            )
            return [Job.from_db_row(dict(row)) for row in cursor.fetchall()]

    def mark_jobs_emailed(self, job_hashes: list[str]) -> None:
        """Mark jobs as emailed."""
        if not job_hashes:
            return

        with self._get_connection() as conn:
            placeholders = ",".join("?" * len(job_hashes))
            conn.execute(
                f"""
                UPDATE jobs
                SET emailed_at = CURRENT_TIMESTAMP
                WHERE job_hash IN ({placeholders})
                """,
                job_hashes,
            )

    def insert_feedback(self, feedback: Feedback) -> None:
        """Insert user feedback."""
        with self._get_connection() as conn:
            data = feedback.to_db_dict()
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            conn.execute(
                f"INSERT INTO feedback ({columns}) VALUES ({placeholders})",
                tuple(data.values()),
            )

    def get_liked_jobs(self, limit: int = 10) -> list[dict]:
        """Get recently liked jobs for feedback context."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT j.title, j.company, j.sector
                FROM feedback f
                JOIN jobs j ON f.job_hash = j.job_hash
                WHERE f.feedback_type = 'like'
                ORDER BY f.created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_disliked_jobs(self, limit: int = 10) -> list[dict]:
        """Get recently disliked jobs for feedback context."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT j.title, j.company, j.sector
                FROM feedback f
                JOIN jobs j ON f.job_hash = j.job_hash
                WHERE f.feedback_type = 'dislike'
                ORDER BY f.created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_job_by_hash(self, job_hash: str) -> Optional[Job]:
        """Get a job by its hash."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE job_hash = ?", (job_hash,)
            )
            row = cursor.fetchone()
            return Job.from_db_row(dict(row)) if row else None

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._get_connection() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) FROM jobs")
            stats["total_jobs"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE relevance_score IS NOT NULL")
            stats["analyzed_jobs"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE relevance_score >= 60")
            stats["relevant_jobs"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE emailed_at IS NOT NULL")
            stats["emailed_jobs"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM feedback")
            stats["total_feedback"] = cursor.fetchone()[0]

            return stats
