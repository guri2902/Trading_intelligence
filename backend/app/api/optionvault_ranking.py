from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..options_backtest.ranking import rank_optionvault_strategies

router = APIRouter(prefix="/backtest/optionvault", tags=["OptionVault Ranking"])


class RankingRequest(BaseModel):
    strategies: list[dict[str, Any]] = Field(default_factory=list)
    top_n: int = Field(default=5, ge=1, le=100)
    min_score: float = Field(default=50.0, ge=0, le=100)
    require_active: bool = True


@router.post("/rank")
def rank(req: RankingRequest) -> dict[str, Any]:
    return rank_optionvault_strategies(
        req.strategies,
        top_n=req.top_n,
        min_score=req.min_score,
        require_active=req.require_active,
    )
