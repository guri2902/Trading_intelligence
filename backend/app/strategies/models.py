from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class StrategyContext(BaseModel):
    timestamp: datetime | str
    candles: list[dict]
    features: dict
    structure: dict
    options: dict | None = None
    regime: str | None = None


class StrategySetup(BaseModel):
    strategy: str
    direction: str  # LONG / SHORT / NONE
    state: str      # TRIGGERED / WATCH / INVALID / NO_SETUP
    entry: float | None = None
    invalidation: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    risk_reward: float | None = None
    confidence: float = Field(default=0.0, ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    invalidation_reasons: list[str] = Field(default_factory=list)
    wait_for: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class StrategyBatchResult(BaseModel):
    timestamp: datetime | str
    setups: list[StrategySetup]
    triggered_count: int
    best_setup: StrategySetup | None = None
    regime: str = "UNKNOWN"
