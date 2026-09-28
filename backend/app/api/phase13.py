from fastapi import APIRouter, HTTPException

from ..agents.models import AgentInput
from ..agents.orchestrator import AgentOrchestrator

router = APIRouter(prefix="/phase13", tags=["phase13"])
orchestrator = AgentOrchestrator()


@router.post("/analyze")
def analyze(data: AgentInput):
    try:
        return orchestrator.run(data).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
