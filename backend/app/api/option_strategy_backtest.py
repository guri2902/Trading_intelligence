from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..options_backtest.strategy_option_bridge import run_strategy_option_backtest
from ..options_backtest.models import OptionsBacktestConfig

router = APIRouter(prefix="/backtest/strategy-options", tags=["Strategy Option Backtest"])


class StrategyOptionBacktestRequest(BaseModel):
    underlying_rows: list[dict] = Field(min_length=15)
    strategy_name: str = Field(min_length=1)
    preferred_strategy: str = Field(min_length=1)
    strike_reference: float
    expiry: str | None = None
    strike_mode: str = "ATM"
    strike_offset: int = 0
    stop_pct: float = Field(default=0.15, gt=0)
    target_rr: float = Field(default=1.5, gt=0)
    config: OptionsBacktestConfig = OptionsBacktestConfig()
    data_provider: str = "upstox"


@router.post("/run")
def run(req: StrategyOptionBacktestRequest):
    try:
        return run_strategy_option_backtest(
            req.underlying_rows,
            strategy_name=req.strategy_name,
            preferred_strategy=req.preferred_strategy,
            strike_reference=req.strike_reference,
            expiry=req.expiry,
            strike_mode=req.strike_mode,
            strike_offset=req.strike_offset,
            stop_pct=req.stop_pct,
            target_rr=req.target_rr,
            config=req.config,
            data_provider=req.data_provider,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
