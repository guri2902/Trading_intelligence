from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..agents.models import AgentInput
from ..agents.orchestrator import AgentOrchestrator
from ..agents.research_context import enrich_agent_input
from ..db.audit import AgentRun, persist_research, persist_run
from ..db.session import get_db
from ..llm.multi_agent import MultiAgentLLMOrchestrator
from ..research_data.models import ResearchBundle

router = APIRouter(prefix="/phase16", tags=["phase16"])


class LLMRunRequest(BaseModel):
    data: AgentInput
    research: ResearchBundle | None = None
    provider: str | None = None
    model: str | None = None
    enabled_agents: list[str] | None = Field(default=None, max_length=20)


def _json(run: AgentRun):
    import json
    return json.loads(run.result_json)


@router.get("/health")
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "phase": 16, "llm_mode": "advisory_only", "agent_runs": db.query(AgentRun).count()}


@router.post("/agent-run")
def agent_run(request: LLMRunRequest, db: Session = Depends(get_db)):
    try:
        enriched = enrich_agent_input(request.data, request.research)
        enabled = tuple(request.enabled_agents) if request.enabled_agents else None
        orchestrator = MultiAgentLLMOrchestrator(
            AgentOrchestrator(), enabled_agents=enabled
        )
        result = orchestrator.run(
            enriched,
            provider=request.provider,
            model=request.model,
        )
        row = persist_run(db, result, enriched.model_dump(mode="json"))
        if request.research is not None:
            persist_research(db, row.id, request.research)
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "action": row.decision_action,
            "direction": row.decision_direction,
            "confidence": row.confidence,
            "score": row.score,
            "debate_winner": row.debate_winner,
            "llm_debate": result.final_decision.metadata.get("llm_debate"),
            "result": _json(row),
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
