
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from validation.walk_forward import WalkForwardValidator

router = APIRouter(prefix="/phase24", tags=["phase24"])


class WalkForwardRequest(BaseModel):
    data: List[float]
    train_size: int = Field(ge=1)
    test_size: int = Field(ge=1)
    step_size: int | None = Field(default=None, ge=1)
    min_windows: int = Field(default=3, ge=1)
    min_oos_trades: int = Field(default=5, ge=0)
    min_oos_win_rate: float | None = Field(default=None, ge=0, le=1)
    max_oos_drawdown_pct: float | None = Field(default=None, ge=0)
    min_positive_windows_pct: float = Field(default=0.60, ge=0, le=1)


@router.get("/health")
def health() -> Dict[str, str]:
    return {"phase": "24", "status": "ok"}


@router.post("/walk-forward")
def walk_forward(req: WalkForwardRequest) -> Dict[str, Any]:
    # The production endpoint will inject the Phase 23 optimizer and Phase 22
    # backtester. This validation API intentionally refuses to fabricate results.
    raise HTTPException(
        status_code=501,
        detail=(
            "Walk-forward orchestration requires the production optimizer/backtest "
            "adapters; this endpoint does not synthesize market metrics."
        ),
    )
