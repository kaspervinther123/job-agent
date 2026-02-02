# Job Agent

An agentic job search assistant that finds relevant Danish job listings using Claude AI.

## Features

- **Multi-source scraping**: Jobindex.dk, Jobnet.dk, and 25+ company career pages
- **AI-powered matching**: Claude analyzes each job against your profile and scores relevance (0-100)
- **Learning from feedback**: The agent improves recommendations based on jobs you like/dislike
- **Daily email digests**: Receive curated job listings at midnight
- **Free hosting**: Runs on GitHub Actions with no server costs

## Quick Start

### 1. Clone and setup

```bash
cd job-agent
cp .env.example .env
# Edit .env with your API keys
```

### 2. Install dependencies

```bash
# Using uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
uv run playwright install chromium

# Or using pip
pip install -e .
playwright install chromium
```

### 3. Configure API keys

You'll need:
- **Anthropic API key**: Get from https://console.anthropic.com/
- **Resend API key**: Get from https://resend.com/ (free tier: 100 emails/day)

Add to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
RESEND_API_KEY=re_...
```

### 4. Run locally

```bash
uv run python -m src.main
```

### 5. Deploy to GitHub Actions

1. Push this repo to GitHub
2. Go to Settings → Secrets and variables → Actions
3. Add secrets:
   - `ANTHROPIC_API_KEY`
   - `RESEND_API_KEY`
4. The workflow runs automatically at midnight (Copenhagen time)

## Configuration

Edit `config.yaml` to customize:

```yaml
scrapers:
  jobindex:
    enabled: true
    search_terms:
      - konsulent
      - analytiker
      - fuldmægtig
    location: Danmark

scoring:
  min_relevance: 60  # Only include jobs scoring >= 60%

email:
  to_address: your-email@example.com
```

## Project Structure

```
job-agent/
├── src/
│   ├── main.py           # Entry point
│   ├── agent.py          # Claude reasoning engine
│   ├── config.py         # Configuration
│   ├── scrapers/         # Job scrapers
│   │   ├── jobindex.py
│   │   ├── jobnet.py
│   │   └── company_pages.py
│   ├── models/           # Data models
│   ├── storage/          # SQLite database
│   └── email/            # Email sending
├── .github/workflows/    # GitHub Actions
├── config.yaml           # Configuration
└── data/                 # Database storage
```

## How It Works

1. **Scrape**: Collects jobs from Jobindex, Jobnet, and company career pages
2. **Deduplicate**: Removes duplicate listings across sources
3. **Analyze**: Claude scores each job's relevance to your profile (0-100)
4. **Filter**: Only jobs scoring 60+ are included
5. **Email**: Sends a digest grouped by sector with highlights/concerns

## Providing Feedback

After receiving jobs, you can provide feedback to improve future recommendations:

```bash
# Like a job
uv run python -c "
from src.storage import Database
from src.models.feedback import Feedback, FeedbackType
db = Database()
db.insert_feedback(Feedback(job_hash='abc123', feedback_type=FeedbackType.LIKE))
"
```

The agent will learn from your feedback and adjust future scoring.

## License

MIT
