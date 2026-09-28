from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.models import AgentInput
from ..agents.orchestrator import AgentOrchestrator
from ..agents.research_context import enrich_agent_input
from ..db.audit import AgentPerformance, AgentRun, AgentRunRecord, DecisionOutcome, persist_research, persist_run, record_outcome
from ..db.session import get_db
from ..research_data.models import ResearchBundle

router = APIRouter(prefix="/phase15", tags=["phase15"])
orchestrator = AgentOrchestrator()


class AgentRunRequest(BaseModel):
    data: AgentInput
    research: ResearchBundle | None = None


class OutcomeRequest(BaseModel):
    run_id: int
    realized_direction: str = Field(pattern="^(LONG|SHORT|NONE)$")
    pnl: float | None = None
    return_pct: float | None = None
    holding_minutes: float | None = Field(default=None, ge=0)
    exit_reason: str | None = None
    notes: str | None = None


def _run_json(row: AgentRun):
    return {
        "id": row.id,
        "run_key": row.run_key,
        "timestamp": row.timestamp.isoformat(),
        "symbol": row.symbol,
        "decision": {
            "action": row.decision_action,
            "direction": row.decision_direction,
            "confidence": row.confidence,
            "score": row.score,
        },
        "debate_winner": row.debate_winner,
        "risk_veto": row.risk_veto,
        "qa_pass": row.qa_pass,
        "input_hash": row.input_hash,
        "result": json.loads(row.result_json),
    }


@router.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "phase": 15,
        "agent_runs": db.query(AgentRun).count(),
        "outcomes": db.query(DecisionOutcome).count(),
        "agents_evaluated": db.query(AgentPerformance).count(),
    }


@router.post("/agent-run")
def agent_run(request: AgentRunRequest, db: Session = Depends(get_db)):
    try:
        enriched = enrich_agent_input(request.data, request.research)
        result = orchestrator.run(enriched)
        input_payload = enriched.model_dump(mode="json")
        row = persist_run(db, result, input_payload)
        if request.research is not None:
            persist_research(db, row.id, request.research)
        db.commit()
        db.refresh(row)
        return _run_json(row)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runs")
def list_runs(
    limit: int = Query(default=50, ge=1, le=500),
    symbol: str | None = None,
    action: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)
    if symbol:
        stmt = stmt.where(AgentRun.symbol == symbol)
    if action:
        stmt = stmt.where(AgentRun.decision_action == action)
    rows = db.scalars(stmt).all()
    return [_run_json(row) for row in rows]


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    row = db.get(AgentRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    records = db.scalars(select(AgentRunRecord).where(AgentRunRecord.run_id == run_id)).all()
    outcome = db.scalar(select(DecisionOutcome).where(DecisionOutcome.run_id == run_id))
    payload = _run_json(row)
    payload["agent_records"] = [
        {
            "agent": r.agent_name,
            "stance": r.stance,
            "score": r.score,
            "confidence": r.confidence,
            "evidence": json.loads(r.evidence_json),
            "risks": json.loads(r.risks_json),
            "questions": json.loads(r.questions_json),
            "metadata": json.loads(r.metadata_json),
            "provider": r.provider,
            "model": r.model,
            "prompt_hash": r.prompt_hash,
            "result_hash": r.result_hash,
            "latency_ms": r.latency_ms,
        }
        for r in records
    ]
    if outcome:
        payload["outcome"] = {
            "realized_direction": outcome.realized_direction,
            "pnl": outcome.pnl,
            "return_pct": outcome.return_pct,
            "won": outcome.won,
            "holding_minutes": outcome.holding_minutes,
            "exit_reason": outcome.exit_reason,
            "notes": outcome.notes,
        }
    return payload


@router.post("/outcomes")
def create_outcome(request: OutcomeRequest, db: Session = Depends(get_db)):
    run = db.get(AgentRun, request.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    try:
        # For an evaluated trade, direction must match the realized underlying direction.
        # A prior no-trade decision is only marked successful when no adverse directional move is supplied.
        pnl = request.pnl
        won = (
            (run.decision_direction == request.realized_direction and run.decision_direction != "NONE")
            or (run.decision_direction == "NONE" and (pnl is None or pnl >= 0))
        )
        outcome = record_outcome(
            db,
            request.run_id,
            request.realized_direction,
            pnl=pnl,
            return_pct=request.return_pct,
            holding_minutes=request.holding_minutes,
            exit_reason=request.exit_reason,
            notes=request.notes,
        )
        outcome.won = won
        db.commit()
        return {
            "run_id": request.run_id,
            "realized_direction": outcome.realized_direction,
            "won": outcome.won,
            "pnl": outcome.pnl,
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/performance")
def performance(db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentPerformance).order_by(AgentPerformance.agent_name)).all()
    return [
        {
            "agent": r.agent_name,
            "evaluated_runs": r.evaluated_runs,
            "directional_accuracy": round(r.correct_direction / r.evaluated_runs, 4) if r.evaluated_runs else None,
            "avg_score": round(r.avg_score, 3),
            "avg_confidence": round(r.avg_confidence, 3),
            "useful_vetoes": r.useful_vetoes,
            "last_evaluated_at": r.last_evaluated_at.isoformat() if r.last_evaluated_at else None,
        }
        for r in rows
    ]
