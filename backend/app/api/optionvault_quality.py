from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..options_backtest.quality import QualityConfig, score_optionvault_strategy

router = APIRouter(prefix="/backtest/optionvault", tags=["OptionVault Quality"])


class QualityRequest(BaseModel):
    qualification: dict = Field(default_factory=dict)
    walkforward: dict = Field(default_factory=dict)
    robustness: dict = Field(default_factory=dict)
    regime: dict = Field(default_factory=dict)
    config: QualityConfig = Field(default_factory=QualityConfig)


@router.post("/quality")
def quality(req: QualityRequest):
    try:
        return score_optionvault_strategy(
            qualification=req.qualification,
            walkforward=req.walkforward,
            robustness=req.robustness,
            regime=req.regime,
            config=req.config,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
