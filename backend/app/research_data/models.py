from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SourceAttribution(BaseModel):
    source: str
    source_type: str
    url: str | None = None
    retrieved_at: datetime
    provider: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)


class FundamentalSnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    score: float = 0.0
    confidence: float = 0.0
    summary: str = ""
    metrics: dict[str, float | str | None] = {}
    risks: list[str] = []
    sources: list[SourceAttribution] = []


class SentimentSnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    score: float = 0.0
    confidence: float = 0.0
    positive_items: int = 0
    negative_items: int = 0
    neutral_items: int = 0
    summary: str = ""
    sources: list[SourceAttribution] = []


class NewsItem(BaseModel):
    headline: str
    timestamp: datetime
    symbol: str | None = None
    source: str
    url: str | None = None
    sentiment: float | None = None
    impact: str = "UNKNOWN"


class NewsMacroSnapshot(BaseModel):
    symbol: str | None
    timestamp: datetime
    score: float = 0.0
    confidence: float = 0.0
    high_impact_event: bool = False
    summary: str = ""
    risks: list[str] = []
    items: list[NewsItem] = []
    sources: list[SourceAttribution] = []


class ResearchBundle(BaseModel):
    symbol: str
    timestamp: datetime
    fundamentals: FundamentalSnapshot | None = None
    sentiment: SentimentSnapshot | None = None
    news: NewsMacroSnapshot | None = None
