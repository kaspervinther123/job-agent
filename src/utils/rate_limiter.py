"""Rate limiting utilities."""

import asyncio
import time
from typing import Optional


class RateLimiter:
    """Simple rate limiter for scraping."""

    def __init__(self, requests_per_second: float = 1.0):
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second
        """
        self.min_interval = 1.0 / requests_per_second
        self.last_request: Optional[float] = None

    async def wait(self) -> None:
        """Wait until the next request is allowed."""
        if self.last_request is not None:
            elapsed = time.time() - self.last_request
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)

        self.last_request = time.time()
