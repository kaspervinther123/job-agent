"""Email sender for job digests."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import resend
from jinja2 import Environment, FileSystemLoader

from ..models.job import Job
from ..config import settings

logger = logging.getLogger(__name__)


class EmailSender:
    """Send job digest emails via Resend."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_address: str = "Job Agent <onboarding@resend.dev>",
        to_address: str = "kaspervinther123@gmail.com",
    ):
        """Initialize the email sender.

        Args:
            api_key: Resend API key
            from_address: Sender email address
            to_address: Recipient email address
        """
        self.api_key = api_key or settings.resend_api_key
        self.from_address = from_address
        self.to_address = to_address

        resend.api_key = self.api_key

        # Set up Jinja2 template environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
        )

    def _group_jobs_by_sector(self, jobs: list[Job]) -> dict[str, list[Job]]:
        """Group jobs by sector for display."""
        sector_names = {
            "konsulent": "Konsulent & Rådgivning",
            "offentlig": "Offentlig Sektor",
            "interesseorganisation": "Interesseorganisationer",
            "velgoerende": "Velgørende Organisationer",
            "virksomhed": "Private Virksomheder",
            None: "Øvrige",
        }

        grouped: dict[str, list[Job]] = {}

        for job in jobs:
            sector_key = job.sector or None
            sector_name = sector_names.get(sector_key, sector_key or "Øvrige")

            if sector_name not in grouped:
                grouped[sector_name] = []
            grouped[sector_name].append(job)

        # Sort jobs within each sector by relevance score
        for sector in grouped:
            grouped[sector].sort(key=lambda j: j.relevance_score or 0, reverse=True)

        return grouped

    def render_digest(self, jobs: list[Job]) -> str:
        """Render the digest email HTML.

        Args:
            jobs: List of jobs to include in the digest

        Returns:
            Rendered HTML string
        """
        template = self.jinja_env.get_template("digest.html")

        jobs_by_sector = self._group_jobs_by_sector(jobs)

        return template.render(
            jobs_by_sector=jobs_by_sector,
            total_jobs=len(jobs),
            date=datetime.now().strftime("%d. %B %Y"),
        )

    def send_digest(self, jobs: list[Job]) -> bool:
        """Send a job digest email.

        Args:
            jobs: List of jobs to include in the digest

        Returns:
            True if sent successfully, False otherwise
        """
        if not jobs:
            logger.info("No jobs to send in digest")
            return True

        if not self.api_key:
            logger.error("No Resend API key configured - RESEND_API_KEY env var is empty")
            return False

        logger.info(f"Preparing to send email to {self.to_address} from {self.from_address}")

        try:
            html_content = self.render_digest(jobs)

            # Create subject with job count
            high_match_count = sum(1 for j in jobs if (j.relevance_score or 0) >= 80)
            if high_match_count > 0:
                subject = f"🎯 {len(jobs)} nye jobs - {high_match_count} stærke matches!"
            else:
                subject = f"📋 {len(jobs)} nye relevante jobopslag"

            # Send via Resend
            params = {
                "from": self.from_address,
                "to": [self.to_address],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)

            logger.info(f"Sent digest email with {len(jobs)} jobs. ID: {response.get('id')}")
            return True

        except Exception as e:
            logger.error(f"Failed to send digest email: {e}")
            return False

    def send_test_email(self) -> bool:
        """Send a test email to verify configuration.

        Returns:
            True if sent successfully
        """
        try:
            params = {
                "from": self.from_address,
                "to": [self.to_address],
                "subject": "Job Agent - Test Email",
                "html": """
                <h1>Test Email</h1>
                <p>If you received this, your Job Agent email configuration is working correctly!</p>
                <p>Sent at: {}</p>
                """.format(datetime.now().isoformat()),
            }

            response = resend.Emails.send(params)
            logger.info(f"Sent test email. ID: {response.get('id')}")
            return True

        except Exception as e:
            logger.error(f"Failed to send test email: {e}")
            return False
