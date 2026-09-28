
from __future__ import annotations
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from self_improvement.engine import (
    CandidateEvaluation, ImprovementCandidate, SelfImprovementEngine
)

router = APIRouter(prefix="/phase26", tags=["phase26"])


class CandidateInput(BaseModel):
    candidate_id: str
    base_version: str
    params: Dict[str, Any]
    rationale: str = ""


class ImprovementRequest(BaseModel):
    signal_context: Dict[str, Any]
    current_version: str
    outcome: Dict[str, Any]
    agent_feedback: Dict[str, Any] = {}
    candidates: List[CandidateInput] = []
    evaluations: Dict[str, Dict[str, Any]] = {}


@router.get("/health")
def health() -> Dict[str, str]:
    return {"phase": "26", "status": "ok"}


@router.post("/evaluate")
def evaluate(req: ImprovementRequest) -> Dict[str, Any]:
    # Production integration injects candidate generator + evaluator from
    # Phase 23/24/25. This API refuses to invent test results.
    if not req.candidates or not req.evaluations:
        raise HTTPException(
            status_code=400,
            detail="Real candidate evaluations are required; Phase 26 does not synthesize performance."
        )

    def generator(_ctx, _version):
        return [ImprovementCandidate(c.candidate_id, c.base_version, c.params, c.rationale)
                for c in req.candidates]

    def evaluator(candidate):
        data = req.evaluations.get(candidate.candidate_id)
        if data is None:
            raise ValueError(f"missing evaluation for {candidate.candidate_id}")
        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            in_sample=data.get("in_sample", {}),
            out_of_sample=data.get("out_of_sample", {}),
            baseline_oos=data.get("baseline_oos", {}),
            improvement_pct=data.get("improvement_pct", {}),
            eligible=bool(data.get("eligible", False)),
            reasons=list(data.get("reasons", [])),
        )

    engine = SelfImprovementEngine(generator, evaluator)
    record = engine.improve(
        signal_context=req.signal_context,
        current_version=req.current_version,
        outcome=req.outcome,
        agent_feedback=req.agent_feedback,
    )
    return {
        "signal_id": record.signal_id,
        "candidate_ids": record.candidate_ids,
        "promotion": record.promotion.__dict__,
    }
