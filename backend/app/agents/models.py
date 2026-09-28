from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentInput(BaseModel):
    timestamp: datetime | str
    market: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)
    structure: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    strategies: dict[str, Any] = Field(default_factory=dict)
    ml: dict[str, Any] = Field(default_factory=dict)
    fundamentals: dict[str, Any] = Field(default_factory=dict)
    sentiment: dict[str, Any] = Field(default_factory=dict)
    news: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    source: str
    statement: str
    strength: float = Field(default=0.0, ge=0, le=100)


class AgentVerdict(BaseModel):
    agent: str
    stance: str  # BULLISH / BEARISH / NEUTRAL / VETO / UNKNOWN
    score: float = Field(default=0.0, ge=-100, le=100)
    confidence: float = Field(default=0.0, ge=0, le=100)
    evidence: list[Evidence] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DebateResult(BaseModel):
    ce_case: AgentVerdict
    pe_case: AgentVerdict
    contrarian: AgentVerdict
    winner: str  # CE / PE / NO_TRADE
    ce_score: float
    pe_score: float
    reason: str
    unresolved_conflicts: list[str] = Field(default_factory=list)


class FinalDecision(BaseModel):
    action: str  # BUY_CE / BUY_PE / WAIT / NO_TRADE
    direction: str  # LONG / SHORT / NONE
    confidence: float = Field(default=0.0, ge=0, le=100)
    score: float = Field(default=0.0, ge=-100, le=100)
    rationale: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    debate: DebateResult | None = None
    risk_veto: bool = False
    qa_pass: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunResult(BaseModel):
    timestamp: datetime | str
    agents: list[AgentVerdict]
    debate: DebateResult
    final_decision: FinalDecision
