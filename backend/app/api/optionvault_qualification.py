from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..options_backtest.qualification import QualificationConfig, qualify_optionvault_research

router = APIRouter(prefix="/backtest/optionvault", tags=["OptionVault Qualification"])


class QualificationRequest(BaseModel):
    walkforward: dict = Field(default_factory=dict)
    robustness: dict = Field(default_factory=dict)
    regime: dict = Field(default_factory=dict)
    config: QualificationConfig = Field(default_factory=QualificationConfig)


@router.post("/qualification")
def qualification(req: QualificationRequest):
    try:
        return qualify_optionvault_research(
            walkforward=req.walkforward,
            robustness=req.robustness,
            regime=req.regime,
            config=req.config,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
