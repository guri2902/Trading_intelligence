from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .models import Base


def _json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    symbol: Mapped[str | None] = mapped_column(String(80), index=True)
    decision_action: Mapped[str | None] = mapped_column(String(30), index=True)
    decision_direction: Mapped[str | None] = mapped_column(String(20), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    debate_winner: Mapped[str | None] = mapped_column(String(20))
    risk_veto: Mapped[bool] = mapped_column(Boolean, default=False)
    qa_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    input_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentRunRecord(Base):
    __tablename__ = "agent_run_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(80), index=True)
    stance: Mapped[str] = mapped_column(String(30), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_json: Mapped[str] = mapped_column(Text)
    risks_json: Mapped[str] = mapped_column(Text)
    questions_json: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    result_hash: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResearchSnapshotRecord(Base):
    __tablename__ = "research_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DecisionOutcome(Base):
    __tablename__ = "decision_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), unique=True, index=True)
    realized_direction: Mapped[str] = mapped_column(String(20))
    pnl: Mapped[float | None] = mapped_column(Float)
    return_pct: Mapped[float | None] = mapped_column(Float)
    won: Mapped[bool] = mapped_column(Boolean, default=False)
    holding_minutes: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentPerformance(Base):
    __tablename__ = "agent_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    evaluated_runs: Mapped[int] = mapped_column(Integer, default=0)
    correct_direction: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    useful_vetoes: Mapped[int] = mapped_column(Integer, default=0)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def persist_run(db: Session, result: Any, input_payload: dict[str, Any]) -> AgentRun:
    now = datetime.now(timezone.utc)
    payload = result.model_dump(mode="json")
    final = result.final_decision
    symbol = None
    market = input_payload.get("market") or {}
    symbol = market.get("symbol") or market.get("instrument") or input_payload.get("symbol")
    run = AgentRun(
        run_key=sha256_json({"timestamp": str(result.timestamp), "input": input_payload})[:32],
        timestamp=result.timestamp if isinstance(result.timestamp, datetime) else now,
        symbol=symbol,
        decision_action=final.action,
        decision_direction=final.direction,
        confidence=final.confidence,
        score=final.score,
        debate_winner=result.debate.winner,
        risk_veto=final.risk_veto,
        qa_pass=final.qa_pass,
        input_hash=sha256_json(input_payload),
        result_json=_json(payload),
        created_at=now,
    )
    db.add(run)
    db.flush()
    for verdict in result.agents:
        meta = verdict.metadata or {}
        db.add(AgentRunRecord(
            run_id=run.id,
            agent_name=verdict.agent,
            stance=verdict.stance,
            score=verdict.score,
            confidence=verdict.confidence,
            evidence_json=_json([e.model_dump(mode="json") for e in verdict.evidence]),
            risks_json=_json(verdict.risks),
            questions_json=_json(verdict.questions),
            metadata_json=_json(meta),
            provider=meta.get("provider"),
            model=meta.get("model"),
            prompt_hash=meta.get("prompt_hash"),
            result_hash=sha256_json(verdict.model_dump(mode="json")),
            latency_ms=meta.get("latency_ms"),
            created_at=now,
        ))
    return run


def persist_research(db: Session, run_id: int, bundle: Any) -> ResearchSnapshotRecord:
    payload = bundle.model_dump(mode="json") if hasattr(bundle, "model_dump") else bundle
    symbol = payload.get("symbol", "UNKNOWN")
    row = ResearchSnapshotRecord(
        run_id=run_id,
        symbol=symbol,
        snapshot_json=_json(payload),
        input_hash=sha256_json(payload),
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    return row


def record_outcome(db: Session, run_id: int, realized_direction: str, *, pnl: float | None = None,
                   return_pct: float | None = None, holding_minutes: float | None = None,
                   exit_reason: str | None = None, notes: str | None = None) -> DecisionOutcome:
    direction = realized_direction.upper()
    won = False
    outcome = DecisionOutcome(
        run_id=run_id,
        realized_direction=direction,
        pnl=pnl,
        return_pct=return_pct,
        won=bool(won),
        holding_minutes=holding_minutes,
        exit_reason=exit_reason,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )
    existing = db.scalar(select(DecisionOutcome).where(DecisionOutcome.run_id == run_id))
    if existing:
        existing.realized_direction = direction
        existing.pnl = pnl
        existing.return_pct = return_pct
        existing.won = bool(won)
        existing.holding_minutes = holding_minutes
        existing.exit_reason = exit_reason
        existing.notes = notes
        outcome = existing
    else:
        db.add(outcome)
        db.flush()
    _rebuild_agent_performance(db, run_id, outcome)
    return outcome


def _rebuild_agent_performance(db: Session, run_id: int, outcome: DecisionOutcome) -> None:
    run_records = db.scalars(select(AgentRunRecord).where(AgentRunRecord.run_id == run_id)).all()
    for rec in run_records:
        perf = db.scalar(select(AgentPerformance).where(AgentPerformance.agent_name == rec.agent_name))
        if perf is None:
            perf = AgentPerformance(agent_name=rec.agent_name)
            db.add(perf)
            db.flush()
        perf.evaluated_runs += 1
        decision_direction = "LONG" if rec.stance == "BULLISH" else "SHORT" if rec.stance == "BEARISH" else "NONE"
        correct = decision_direction == outcome.realized_direction and decision_direction != "NONE"
        if correct:
            perf.correct_direction += 1
        perf.avg_score = ((perf.avg_score * (perf.evaluated_runs - 1)) + rec.score) / perf.evaluated_runs
        perf.avg_confidence = ((perf.avg_confidence * (perf.evaluated_runs - 1)) + rec.confidence) / perf.evaluated_runs
        perf.last_evaluated_at = datetime.now(timezone.utc)
        if rec.stance == "VETO" and not outcome.won:
            perf.useful_vetoes += 1
