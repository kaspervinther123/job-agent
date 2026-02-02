"""Claude reasoning engine for job relevance scoring."""

import json
import logging
from typing import Optional

import anthropic

from .models.job import Job
from .models.profile import CandidateProfile
from .models.feedback import format_feedback_for_prompt
from .config import settings

logger = logging.getLogger(__name__)

RELEVANCE_PROMPT = """You are a job matching assistant helping a candidate find relevant positions.
Analyze the job posting against the candidate's profile and provide a relevance score.

{profile}

## Feedback History (what the candidate liked/disliked)
{feedback}

---

## Job Posting to Analyze

**Title:** {title}
**Company:** {company}
**Location:** {location}
**Sector:** {sector}

**Description:**
{description}

---

## Your Task

Analyze how well this job matches the candidate's profile, experience, and preferences.
Consider:
1. Does the role match their education and skills?
2. Is the company/sector aligned with their interests?
3. Does the location work for them?
4. Is the seniority level appropriate (they are a recent graduate)?
5. Does it match patterns from jobs they liked/disliked?

Provide your analysis in JSON format:

```json
{{
    "score": <0-100>,
    "reasoning": "<2-3 sentence explanation of the match quality>",
    "highlights": ["<positive aspect 1>", "<positive aspect 2>"],
    "concerns": ["<concern 1>", "<concern 2>"]
}}
```

Score guidelines:
- 80-100: Excellent match - directly relevant to their profile and preferences
- 60-79: Good match - mostly aligned, minor gaps
- 40-59: Moderate match - some relevance but significant gaps
- 20-39: Weak match - limited alignment
- 0-19: Poor match - not suitable

Respond ONLY with the JSON, no additional text."""


class JobRelevanceAgent:
    """Agent that uses Claude to score job relevance."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the agent.

        Args:
            api_key: Anthropic API key (defaults to settings)
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.profile = CandidateProfile()

    async def analyze_job(
        self,
        job: Job,
        liked_jobs: list[dict] = None,
        disliked_jobs: list[dict] = None,
    ) -> dict:
        """Analyze a single job's relevance.

        Args:
            job: The job to analyze
            liked_jobs: Jobs the user has liked
            disliked_jobs: Jobs the user has disliked

        Returns:
            Dict with score, reasoning, highlights, concerns
        """
        feedback_text = format_feedback_for_prompt(
            liked_jobs or [],
            disliked_jobs or [],
        )

        prompt = RELEVANCE_PROMPT.format(
            profile=self.profile.to_prompt_text(),
            feedback=feedback_text,
            title=job.title,
            company=job.company,
            location=job.location,
            sector=job.sector or "Unknown",
            description=job.description[:2000],  # Limit description length
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse JSON response
            content = response.content[0].text.strip()

            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            return {
                "score": int(result.get("score", 50)),
                "reasoning": result.get("reasoning", ""),
                "highlights": result.get("highlights", []),
                "concerns": result.get("concerns", []),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            return {
                "score": 50,
                "reasoning": "Analysis failed - could not parse response",
                "highlights": [],
                "concerns": ["Analysis error"],
            }
        except Exception as e:
            logger.error(f"Error analyzing job: {e}")
            return {
                "score": 50,
                "reasoning": f"Analysis failed: {str(e)}",
                "highlights": [],
                "concerns": ["Analysis error"],
            }

    async def analyze_jobs_batch(
        self,
        jobs: list[Job],
        liked_jobs: list[dict] = None,
        disliked_jobs: list[dict] = None,
    ) -> list[tuple[Job, dict]]:
        """Analyze multiple jobs.

        For efficiency, this could batch jobs into a single prompt,
        but for now we process them sequentially to ensure quality.

        Args:
            jobs: List of jobs to analyze
            liked_jobs: Jobs the user has liked
            disliked_jobs: Jobs the user has disliked

        Returns:
            List of (job, analysis) tuples
        """
        results = []

        for job in jobs:
            logger.info(f"Analyzing: {job.title} at {job.company}")
            analysis = await self.analyze_job(job, liked_jobs, disliked_jobs)
            results.append((job, analysis))

            # Log the result
            logger.info(
                f"  Score: {analysis['score']} - {analysis['reasoning'][:100]}..."
            )

        return results
