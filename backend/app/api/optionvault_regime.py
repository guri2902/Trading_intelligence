from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..options_backtest.regime import analyze_trade_history
from ..options_backtest.walkforward import run_optionvault_walkforward
from ..options_backtest.models import OptionsBacktestConfig

router = APIRouter(prefix="/backtest/optionvault", tags=["OptionVault Regime"])


class OptionVaultRegimeRequest(BaseModel):
    underlying_rows: list[dict] = Field(min_length=30)
    strategy_name: str = Field(min_length=1)
    preferred_strategy: str = Field(min_length=1)
    strike_reference: float
    expiry: str | None = None
    strike_mode: str = "ATM"
    strike_offset: int = 0
    stop_pct: float = Field(default=0.15, gt=0)
    target_rr: float = Field(default=1.5, gt=0)
    config: OptionsBacktestConfig = OptionsBacktestConfig()
    train_size: int = Field(default=120, gt=0)
    validation_size: int = Field(default=40, gt=0)
    oos_size: int = Field(default=40, gt=0)
    step: int = Field(default=40, gt=0)
    expanding: bool = True


@router.post("/regime")
def regime(req: OptionVaultRegimeRequest):
    try:
        wf = run_optionvault_walkforward(**req.model_dump())
        return {
            "data_source": "OptionVault",
            "used_actual_option_prices": True,
            "walk_forward": wf["walk_forward"],
            "oos_summary": wf["oos_summary"],
            "regime_analysis": analyze_trade_history(req.underlying_rows, wf["oos_trade_history"]),
        }
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
