"""Feedback model for learning from user preferences."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """Type of feedback."""

    LIKE = "like"
    DISLIKE = "dislike"


class Feedback(BaseModel):
    """User feedback on a job listing."""

    job_hash: str
    feedback_type: FeedbackType
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "job_hash": self.job_hash,
            "feedback_type": self.feedback_type.value,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "Feedback":
        """Create Feedback from database row."""
        return cls(
            job_hash=row["job_hash"],
            feedback_type=FeedbackType(row["feedback_type"]),
            comment=row.get("comment"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
        )


def format_feedback_for_prompt(liked_jobs: list[dict], disliked_jobs: list[dict]) -> str:
    """Format feedback history for Claude prompt.

    Args:
        liked_jobs: List of job dicts the user liked
        disliked_jobs: List of job dicts the user disliked

    Returns:
        Formatted string for inclusion in Claude prompt
    """
    if not liked_jobs and not disliked_jobs:
        return "No feedback history yet."

    sections = []

    if liked_jobs:
        liked_section = "### Jobs the candidate LIKED:\n"
        for job in liked_jobs[:5]:  # Limit to 5 most recent
            liked_section += f"- {job['title']} at {job['company']} ({job.get('sector', 'unknown sector')})\n"
        sections.append(liked_section)

    if disliked_jobs:
        disliked_section = "### Jobs the candidate DISLIKED:\n"
        for job in disliked_jobs[:5]:  # Limit to 5 most recent
            disliked_section += f"- {job['title']} at {job['company']} ({job.get('sector', 'unknown sector')})\n"
        sections.append(disliked_section)

    return "\n".join(sections)
