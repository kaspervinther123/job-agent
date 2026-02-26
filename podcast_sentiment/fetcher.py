"""Fetch and parse podcast RSS feeds using stdlib only."""

import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
import html
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


@dataclass
class Episode:
    title: str
    description: str
    pub_date: datetime
    link: str = ""


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(date_str: str) -> datetime | None:
    """Parse RFC 2822 date string from RSS."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        # Try common alternative formats
        for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d %b %Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
    return None


def fetch_rss(url: str, max_retries: int = 3) -> str:
    """Fetch RSS feed XML content with retries."""
    headers = {
        "User-Agent": "PodcastSentimentTracker/1.0",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  Retry {attempt + 1}/{max_retries} after {wait}s: {e}")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to fetch RSS after {max_retries} attempts: {e}")


def parse_episodes(xml_content: str, min_date: datetime | None = None) -> list[Episode]:
    """Parse RSS XML into Episode objects, optionally filtering by date."""
    root = ET.fromstring(xml_content)

    # Handle potential namespace prefixes
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    episodes = []
    # RSS 2.0 structure: rss > channel > item
    for item in root.iter("item"):
        title_el = item.find("title")
        desc_el = item.find("description")
        date_el = item.find("pubDate")
        link_el = item.find("link")

        # Also check for content:encoded as fallback for description
        content_encoded = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        raw_desc = ""
        if desc_el is not None and desc_el.text:
            raw_desc = desc_el.text
        elif content_encoded is not None and content_encoded.text:
            raw_desc = content_encoded.text

        description = _strip_html(raw_desc)
        pub_date = _parse_date(date_el.text) if date_el is not None and date_el.text else None
        link = link_el.text.strip() if link_el is not None and link_el.text else ""

        if not pub_date:
            continue

        if min_date and pub_date < min_date:
            continue

        if not description and not title:
            continue

        episodes.append(Episode(
            title=title,
            description=description,
            pub_date=pub_date,
            link=link,
        ))

    # Sort chronologically
    episodes.sort(key=lambda e: e.pub_date)
    return episodes


def fetch_podcast_episodes(
    rss_url: str,
    years_back: int = 10,
) -> list[Episode]:
    """Fetch podcast episodes from RSS feed going back N years."""
    min_date = datetime(
        datetime.now(timezone.utc).year - years_back, 1, 1,
        tzinfo=timezone.utc,
    )
    print(f"Fetching RSS feed from {rss_url}...")
    xml_content = fetch_rss(rss_url)
    print(f"Parsing episodes (from {min_date.year} onwards)...")
    episodes = parse_episodes(xml_content, min_date=min_date)
    print(f"Found {len(episodes)} episodes since {min_date.year}")
    return episodes
