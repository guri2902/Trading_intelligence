from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreComponent(BaseModel):
    name: str
    raw: float
    weighted: float
    weight: float
    evidence: list[str] = Field(default_factory=list)


class TradePlan(BaseModel):
    option_type: str = "NONE"
    strike: float | None = None
    expiry: str | None = None
    entry: float | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    risk_reward: float | None = None
    quantity: int | None = None
    lot_size: int | None = None
    contract_source: str | None = None
    invalidation: list[str] = Field(default_factory=list)


class SignalCandidate(BaseModel):
    action: str
    direction: str
    score: float
    confidence: float
    rank_score: float
    option_type: str
    strike: float | None = None
    expiry: str | None = None
    plan: TradePlan | None = None
    components: list[ScoreComponent] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class SignalDecision(BaseModel):
    timestamp: str
    symbol: str | None = None
    action: str
    direction: str
    confidence: float
    score: float
    selected: SignalCandidate | None = None
    candidates: list[SignalCandidate] = Field(default_factory=list)
    hard_gates: list[str] = Field(default_factory=list)
    policy: str = "Deterministic risk/data gates are authoritative; AI is advisory."
