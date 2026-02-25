"""Sentiment analysis for Danish podcast descriptions.

Uses a custom AFINN-based Danish sentiment lexicon for polarity scoring
and a discrete emotion lexicon for Plutchik's 8 basic emotions.
"""

import re
from dataclasses import dataclass, field

from .danish_lexicon import AFINN_DA, EMOTION_LEXICON


@dataclass
class SentimentResult:
    """Sentiment analysis result for a single text."""
    polarity_score: float  # Normalized: -1.0 to 1.0
    raw_score: int         # Sum of word scores
    word_count: int        # Total words analyzed
    matched_words: int     # Words found in lexicon
    label: str             # "positive", "negative", "neutral"
    emotions: dict[str, float] = field(default_factory=dict)  # emotion -> intensity (0-1)
    emotion_words: dict[str, list[str]] = field(default_factory=dict)  # emotion -> matched words


def _tokenize(text: str) -> list[str]:
    """Tokenize Danish text into lowercase words."""
    text = text.lower()
    # Keep Danish special characters: æøå
    text = re.sub(r"[^a-zæøåé0-9\s-]", " ", text)
    words = text.split()
    return [w.strip("-") for w in words if len(w.strip("-")) > 1]


def _handle_negation(words: list[str]) -> list[tuple[str, int]]:
    """Detect negation words and flag following words.

    Returns list of (word, negation_multiplier) tuples.
    """
    negation_words = {"ikke", "ingen", "aldrig", "hverken", "ej", "intet", "uden"}
    result = []
    negate_next = 0
    for word in words:
        if word in negation_words:
            negate_next = 2  # Negate the next 2 words
            result.append((word, 1))
        elif negate_next > 0:
            result.append((word, -1))
            negate_next -= 1
        else:
            result.append((word, 1))
    return result


def analyze_polarity(text: str) -> tuple[float, int, int, int]:
    """Analyze sentiment polarity of Danish text.

    Returns: (normalized_score, raw_score, word_count, matched_words)
    """
    words = _tokenize(text)
    if not words:
        return 0.0, 0, 0, 0

    tagged = _handle_negation(words)
    raw_score = 0
    matched = 0

    for word, multiplier in tagged:
        if word in AFINN_DA:
            raw_score += AFINN_DA[word] * multiplier
            matched += 1

    # Normalize: divide by number of matched words to get average sentiment
    if matched > 0:
        normalized = raw_score / matched
        # Clamp to [-1, 1] range (max AFINN score is 5)
        normalized = max(-1.0, min(1.0, normalized / 5.0))
    else:
        normalized = 0.0

    return normalized, raw_score, len(words), matched


def analyze_emotions(text: str) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Detect discrete emotions in Danish text.

    Returns: (emotion_scores, emotion_matched_words)
    Scores are normalized 0-1 based on word density.
    """
    words = _tokenize(text)
    if not words:
        return {e: 0.0 for e in EMOTION_LEXICON}, {e: [] for e in EMOTION_LEXICON}

    word_set = set(words)
    total_words = len(words)
    scores = {}
    matched_words = {}

    for emotion, lexicon_words in EMOTION_LEXICON.items():
        matches = word_set.intersection(lexicon_words)
        # Count actual occurrences (not just unique matches)
        count = sum(1 for w in words if w in matches) if matches else 0
        # Normalize by text length, scale up for visibility
        scores[emotion] = min(1.0, (count / total_words) * 10) if total_words > 0 else 0.0
        matched_words[emotion] = sorted(matches)

    return scores, matched_words


def analyze_text(text: str) -> SentimentResult:
    """Full sentiment analysis of a Danish text."""
    normalized, raw, word_count, matched = analyze_polarity(text)
    emotions, emotion_words = analyze_emotions(text)

    if normalized > 0.05:
        label = "positive"
    elif normalized < -0.05:
        label = "negative"
    else:
        label = "neutral"

    return SentimentResult(
        polarity_score=normalized,
        raw_score=raw,
        word_count=word_count,
        matched_words=matched,
        label=label,
        emotions=emotions,
        emotion_words=emotion_words,
    )
