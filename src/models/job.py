"""Job data model."""

from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field, computed_field, field_validator
import hashlib


class Job(BaseModel):
    """A job listing."""

    title: str
    company: str
    location: str
    description: str
    url: str
    source: str  # jobindex, jobunivers, etc.
    sector: Optional[str] = None
    posted_date: Optional[datetime] = None
    deadline: Optional[str] = None  # Keep as string since formats vary
    salary: Optional[str] = None

    # Populated after Claude analysis
    relevance_score: Optional[int] = None  # 0-100
    relevance_reasoning: Optional[str] = None
    concerns: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)

    # Metadata
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    raw_html: Optional[str] = None

    @computed_field
    @property
    def job_hash(self) -> str:
        """Unique hash for deduplication based on title + company + URL."""
        # Use URL for better deduplication
        normalized = f"{self.title.lower().strip()}|{self.company.lower().strip()}|{self.url.lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    @computed_field
    @property
    def is_analyzed(self) -> bool:
        """Whether Claude has analyzed this job."""
        return self.relevance_score is not None

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "job_hash": self.job_hash,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "sector": self.sector,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "deadline": self.deadline,
            "salary": self.salary,
            "relevance_score": self.relevance_score,
            "relevance_reasoning": self.relevance_reasoning,
            "concerns": ",".join(self.concerns) if self.concerns else None,
            "highlights": ",".join(self.highlights) if self.highlights else None,
            "scraped_at": self.scraped_at.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "Job":
        """Create Job from database row."""
        return cls(
            title=row["title"],
            company=row["company"],
            location=row["location"],
            description=row["description"],
            url=row["url"],
            source=row["source"],
            sector=row.get("sector"),
            posted_date=datetime.fromisoformat(row["posted_date"]) if row.get("posted_date") else None,
            deadline=row.get("deadline"),
            salary=row.get("salary"),
            relevance_score=row.get("relevance_score"),
            relevance_reasoning=row.get("relevance_reasoning"),
            concerns=row["concerns"].split(",") if row.get("concerns") else [],
            highlights=row["highlights"].split(",") if row.get("highlights") else [],
            scraped_at=datetime.fromisoformat(row["scraped_at"]) if row.get("scraped_at") else datetime.utcnow(),
        )
