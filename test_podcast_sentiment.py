"""End-to-end test for podcast_sentiment using mock RSS data."""

import os
import tempfile

from podcast_sentiment.fetcher import parse_episodes, Episode
from podcast_sentiment.sentiment import analyze_text, analyze_polarity, analyze_emotions
from podcast_sentiment.excel_report import AnalyzedEpisode, create_report

# --- Mock RSS XML with Danish financial podcast episodes ---
MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Millionærklubben</title>
    <item>
      <title>Aktiemarkedet boomer — rekordstort rally og optimisme</title>
      <description>Vi ser en fantastisk fremgang på markedet med stigning i alle sektorer.
      Investorer er begejstret over vækst og profit. Det er en strålende tid for porteføljen.</description>
      <pubDate>Mon, 15 Jan 2024 08:00:00 +0100</pubDate>
      <link>https://example.com/ep1</link>
    </item>
    <item>
      <title>Krise på markedet — frygt for recession og kollaps</title>
      <description>Bekymring og usikkerhed præger markedet. Faldende aktier og risiko for
      nedgang. Investorer frygter en ny krise med tab og nedtur.</description>
      <pubDate>Thu, 15 Feb 2024 08:00:00 +0100</pubDate>
      <link>https://example.com/ep2</link>
    </item>
    <item>
      <title>Analyse af renteudviklingen og inflationen</title>
      <description>Vi ser på markedet og analyserer den aktuelle situation med rente og
      inflation. En afventende periode med overvejelse om strategi.</description>
      <pubDate>Fri, 15 Mar 2024 08:00:00 +0100</pubDate>
      <link>https://example.com/ep3</link>
    </item>
    <item>
      <title>Skandale og svindel ryster investorerne — vrede og frustration</title>
      <description>En stor skandale med bedrageri har ramt markedet. Investorer er rasende
      og frustreret over manipulation og korruption. Trist og skuffende nyheder.</description>
      <pubDate>Mon, 15 Apr 2024 08:00:00 +0200</pubDate>
      <link>https://example.com/ep4</link>
    </item>
    <item>
      <title>Innovation og nye muligheder — håb for fremtiden</title>
      <description>Spændende innovation og potentiale for vækst. Vi håber på forbedring
      og ser lovende tendenser. En optimistisk udsigt med momentum.</description>
      <pubDate>Wed, 15 May 2024 08:00:00 +0200</pubDate>
      <link>https://example.com/ep5</link>
    </item>
  </channel>
</rss>
"""

def test_parse_episodes():
    """Test RSS parsing."""
    episodes = parse_episodes(MOCK_RSS)
    assert len(episodes) == 5, f"Expected 5 episodes, got {len(episodes)}"
    assert episodes[0].title.startswith("Aktiemarkedet")
    assert episodes[-1].title.startswith("Innovation")
    # Sorted chronologically
    for i in range(len(episodes) - 1):
        assert episodes[i].pub_date <= episodes[i + 1].pub_date
    print("  PASS: RSS parsing works correctly (5 episodes, sorted by date)")


def test_sentiment_analysis():
    """Test sentiment scoring."""
    # Positive text
    pos_result = analyze_text("fantastisk fremgang vækst optimisme succes")
    assert pos_result.polarity_score > 0, f"Expected positive, got {pos_result.polarity_score}"
    assert pos_result.label == "positive"

    # Negative text
    neg_result = analyze_text("krise frygt nedgang tab bekymring")
    assert neg_result.polarity_score < 0, f"Expected negative, got {neg_result.polarity_score}"
    assert neg_result.label == "negative"

    # Neutral text
    neu_result = analyze_text("marked aktier investering analyse strategi")
    assert abs(neu_result.polarity_score) <= 0.05, f"Expected neutral, got {neu_result.polarity_score}"

    print(f"  PASS: Sentiment analysis — positive={pos_result.polarity_score:.3f}, "
          f"negative={neg_result.polarity_score:.3f}, neutral={neu_result.polarity_score:.3f}")


def test_negation_handling():
    """Test negation detection."""
    # "ikke god" should be less positive than "god"
    pos_score, _, _, _ = analyze_polarity("god")
    neg_score, _, _, _ = analyze_polarity("ikke god")
    assert neg_score < pos_score, f"Negation failed: 'ikke god'={neg_score} should be < 'god'={pos_score}"
    print(f"  PASS: Negation handling — 'god'={pos_score:.3f}, 'ikke god'={neg_score:.3f}")


def test_emotion_detection():
    """Test discrete emotion detection."""
    # Joy-heavy text
    joy_scores, joy_words = analyze_emotions("glæde begejstring succes fantastisk triumf")
    assert joy_scores["joy"] > 0, f"Expected joy > 0, got {joy_scores['joy']}"
    assert len(joy_words["joy"]) > 0

    # Fear-heavy text
    fear_scores, fear_words = analyze_emotions("frygt panik krise risiko bekymring")
    assert fear_scores["fear"] > 0, f"Expected fear > 0, got {fear_scores['fear']}"

    print(f"  PASS: Emotion detection — joy={joy_scores['joy']:.3f} ({len(joy_words['joy'])} words), "
          f"fear={fear_scores['fear']:.3f} ({len(fear_words['fear'])} words)")


def test_full_pipeline():
    """Test the full pipeline: parse → analyze → report."""
    episodes = parse_episodes(MOCK_RSS)
    analyzed = []
    for ep in episodes:
        text = f"{ep.title} {ep.description}"
        result = analyze_text(text)
        analyzed.append(AnalyzedEpisode(episode=ep, sentiment=result))

    # Verify sentiment makes sense
    labels = [a.sentiment.label for a in analyzed]
    assert "positive" in labels, "Expected at least one positive episode"
    assert "negative" in labels, "Expected at least one negative episode"

    # Print episode sentiments
    for a in analyzed:
        print(f"    [{a.episode.pub_date.strftime('%Y-%m-%d')}] {a.sentiment.label:>8} "
              f"({a.sentiment.polarity_score:+.3f}) — {a.episode.title[:60]}")

    # Generate Excel report
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        output_path = f.name

    try:
        path = create_report(analyzed, output_path, "Millionærklubben (Test)")
        file_size = os.path.getsize(path)
        assert file_size > 5000, f"Report too small: {file_size} bytes"
        print(f"\n  PASS: Excel report generated — {file_size:,} bytes at {path}")
    finally:
        os.unlink(output_path)


if __name__ == "__main__":
    print("=" * 60)
    print("Podcast Sentiment Tracker — Test Suite")
    print("=" * 60)

    tests = [
        ("RSS Parsing", test_parse_episodes),
        ("Sentiment Analysis", test_sentiment_analysis),
        ("Negation Handling", test_negation_handling),
        ("Emotion Detection", test_emotion_detection),
        ("Full Pipeline (parse → analyze → Excel)", test_full_pipeline),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        print(f"\n[TEST] {name}")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)
