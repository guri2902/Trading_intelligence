from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from .models import NewsItem, SentimentSnapshot


def classify_text_sentiment(text: str) -> float:
    """
    Transparent baseline sentiment scorer.

    This intentionally remains a small deterministic baseline. It is not
    presented as an authoritative sentiment model and can be replaced by a
    validated NLP model later.
    """
    text = text.lower()
    positive = {
        "beat", "growth", "upgrade", "strong", "surge", "record",
        "profit", "bullish", "outperform", "positive",
    }
    negative = {
        "miss", "downgrade", "weak", "fall", "drop", "loss",
        "bearish", "lawsuit", "warning", "negative",
    }

    p = sum(1 for word in positive if word in text)
    n = sum(1 for word in negative if word in text)

    if p == 0 and n == 0:
        return 0.0
    return (p - n) / max(p + n, 1)


def aggregate_sentiment(
    symbol: str,
    items: list[NewsItem],
) -> SentimentSnapshot:
    now = datetime.now(timezone.utc)
    values = []
    positive = negative = neutral = 0

    for item in items:
        value = item.sentiment
        if value is None:
            value = classify_text_sentiment(item.headline)

        value = max(-1.0, min(1.0, float(value)))
        values.append(value)

        if value > 0.15:
            positive += 1
        elif value < -0.15:
            negative += 1
        else:
            neutral += 1

    score = mean(values) * 100 if values else 0.0

    return SentimentSnapshot(
        symbol=symbol,
        timestamp=now,
        score=round(score, 2),
        confidence=min(95.0, 20.0 + len(values) * 3.0),
        positive_items=positive,
        negative_items=negative,
        neutral_items=neutral,
        summary=(
            "Headline sentiment baseline only; not a substitute for validated "
            "market-sentiment modeling."
            if values
            else "No news items available."
        ),
    )
