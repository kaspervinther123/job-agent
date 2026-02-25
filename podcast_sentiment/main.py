"""Main entry point for the Podcast Sentiment Tracker."""

import argparse
import os
import sys
from datetime import datetime, timezone

from .fetcher import fetch_podcast_episodes
from .sentiment import analyze_text
from .excel_report import AnalyzedEpisode, create_report

# Known podcast RSS feeds
KNOWN_FEEDS = {
    "millionaerklubben": "https://www.omnycontent.com/d/playlist/1283f5f4-2508-4981-a99f-acb500e64dcf/27dfeb66-f61a-4fcc-aa6d-ad0800b05139/dc61232c-7e07-438e-981a-ad0800b05142/podcast.rss",
}


def run(
    rss_url: str | None = None,
    podcast_name: str = "Millionærklubben",
    years_back: int = 10,
    output: str | None = None,
):
    """Run the sentiment tracker."""
    if rss_url is None:
        rss_url = KNOWN_FEEDS["millionaerklubben"]

    if output is None:
        safe_name = podcast_name.lower().replace(" ", "_").replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
        output = f"output/{safe_name}_sentiment_{datetime.now().strftime('%Y%m%d')}.xlsx"

    # Create output directory
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else "output", exist_ok=True)

    # Step 1: Fetch episodes
    print("=" * 60)
    print(f"Podcast Sentiment Tracker — {podcast_name}")
    print(f"Looking back {years_back} years")
    print("=" * 60)
    print()

    episodes = fetch_podcast_episodes(rss_url, years_back=years_back)

    if not episodes:
        print("No episodes found! Check the RSS feed URL.")
        sys.exit(1)

    # Step 2: Analyze sentiment
    print(f"\nAnalyzing sentiment for {len(episodes)} episodes...")
    analyzed = []
    pos_count = neg_count = neu_count = 0

    for i, ep in enumerate(episodes):
        # Combine title and description for analysis
        text = f"{ep.title} {ep.description}"
        result = analyze_text(text)
        analyzed.append(AnalyzedEpisode(episode=ep, sentiment=result))

        if result.label == "positive":
            pos_count += 1
        elif result.label == "negative":
            neg_count += 1
        else:
            neu_count += 1

        # Progress indicator
        if (i + 1) % 100 == 0 or i == len(episodes) - 1:
            print(f"  Processed {i + 1}/{len(episodes)} episodes")

    # Step 3: Summary
    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 60}")
    all_scores = [a.sentiment.polarity_score for a in analyzed]
    avg_score = sum(all_scores) / len(all_scores)
    print(f"  Episodes analyzed: {len(analyzed)}")
    print(f"  Date range: {analyzed[0].episode.pub_date.strftime('%Y-%m-%d')} → "
          f"{analyzed[-1].episode.pub_date.strftime('%Y-%m-%d')}")
    print(f"  Average polarity: {avg_score:.4f}")
    print(f"  Positive: {pos_count} ({pos_count/len(analyzed)*100:.1f}%)")
    print(f"  Neutral:  {neu_count} ({neu_count/len(analyzed)*100:.1f}%)")
    print(f"  Negative: {neg_count} ({neg_count/len(analyzed)*100:.1f}%)")

    # Emotion summary
    from collections import defaultdict
    total_emotions = defaultdict(float)
    for a in analyzed:
        for emo, score in a.sentiment.emotions.items():
            total_emotions[emo] += score
    print(f"\n  Emotion averages:")
    for emo in sorted(total_emotions, key=total_emotions.get, reverse=True):
        avg = total_emotions[emo] / len(analyzed)
        bar = "█" * int(avg * 40)
        print(f"    {emo:>13}: {avg:.4f} {bar}")

    # Most positive/negative episodes
    most_pos = max(analyzed, key=lambda a: a.sentiment.polarity_score)
    most_neg = min(analyzed, key=lambda a: a.sentiment.polarity_score)
    print(f"\n  Most positive episode:")
    print(f"    [{most_pos.episode.pub_date.strftime('%Y-%m-%d')}] "
          f"{most_pos.episode.title[:70]} (score: {most_pos.sentiment.polarity_score:.3f})")
    print(f"  Most negative episode:")
    print(f"    [{most_neg.episode.pub_date.strftime('%Y-%m-%d')}] "
          f"{most_neg.episode.title[:70]} (score: {most_neg.sentiment.polarity_score:.3f})")

    # Step 4: Generate Excel report
    print(f"\nGenerating Excel report...")
    path = create_report(analyzed, output, podcast_name)
    print(f"Report saved to: {path}")
    print(f"\nSheets included:")
    print(f"  1. Dashboard     — Key metrics and emotion overview chart")
    print(f"  2. Episodes      — Per-episode sentiment with polarity time series")
    print(f"  3. Monthly Trends — Monthly aggregations with trend + distribution charts")
    print(f"  4. Yearly Overview — Year-by-year summary with emotion breakdown")
    print(f"  5. Emotion Deep Dive — Top 10 episodes per discrete emotion")
    print(f"\n{'=' * 60}")
    print("Done!")

    return path


def main():
    parser = argparse.ArgumentParser(
        description="Podcast Sentiment Tracker — Analyze sentiment in podcast descriptions",
    )
    parser.add_argument(
        "--rss", type=str, default=None,
        help="RSS feed URL (defaults to Millionærklubben)",
    )
    parser.add_argument(
        "--name", type=str, default="Millionærklubben",
        help="Podcast name for the report",
    )
    parser.add_argument(
        "--years", type=int, default=10,
        help="How many years back to analyze (default: 10)",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output Excel file path",
    )
    args = parser.parse_args()
    run(rss_url=args.rss, podcast_name=args.name, years_back=args.years, output=args.output)


if __name__ == "__main__":
    main()
