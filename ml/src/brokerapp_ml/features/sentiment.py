"""News-sentiment features (Phase 5 stub).

Phase 5 ships an interface and a deterministic stub scorer. The real
FinBERT / LLM-based pipeline replaces `RuleBasedSentimentScorer` later
without changing the interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from math import tanh

import polars as pl


@dataclass(frozen=True, slots=True)
class NewsItem:
    """One news headline / story snippet for an asset."""

    asset_symbol: str
    published_at: datetime
    title: str
    body: str | None = None


class SentimentScorer(ABC):
    """Returns a polarity score in `[-1, 1]` per `NewsItem`."""

    @abstractmethod
    def score(self, item: NewsItem) -> float: ...


class RuleBasedSentimentScorer(SentimentScorer):
    """Tiny lexicon-based scorer used as a Phase-5 placeholder.

    Deterministic, fast, terrible. The point is that the rest of the
    pipeline (aggregation, joining onto bars) is exercised end-to-end
    so the FinBERT swap in Phase 5.x is a one-file change.
    """

    POSITIVE = frozenset({"beat", "beats", "growth", "upgrade", "surge", "record", "buy"})
    NEGATIVE = frozenset({"miss", "misses", "downgrade", "fall", "fraud", "lawsuit", "sell"})

    def score(self, item: NewsItem) -> float:
        text = f"{item.title} {item.body or ''}".lower()
        positive = sum(text.count(w) for w in self.POSITIVE)
        negative = sum(text.count(w) for w in self.NEGATIVE)
        return tanh(positive - negative)


def aggregate_to_daily(
    items: list[NewsItem],
    scorer: SentimentScorer,
) -> pl.DataFrame:
    """Aggregate per-item scores into daily mean / count features."""
    if not items:
        return pl.DataFrame(
            schema={
                "time": pl.Datetime(time_zone="UTC"),
                "sentiment_mean": pl.Float64,
                "sentiment_count": pl.Int64,
            },
        )
    rows = [
        {
            "time": item.published_at,
            "score": scorer.score(item),
        }
        for item in items
    ]
    frame = pl.from_dicts(rows)
    frame = frame.with_columns(pl.col("time").cast(pl.Datetime(time_zone="UTC")))
    return (
        frame.with_columns(pl.col("time").dt.truncate("1d").alias("time"))
        .group_by("time")
        .agg(
            pl.col("score").mean().alias("sentiment_mean"),
            pl.col("score").count().alias("sentiment_count"),
        )
        .sort("time")
    )


__all__ = [
    "NewsItem",
    "RuleBasedSentimentScorer",
    "SentimentScorer",
    "aggregate_to_daily",
]
