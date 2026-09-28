from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..options_backtest.walkforward import run_optionvault_walkforward
from ..options_backtest.models import OptionsBacktestConfig

router = APIRouter(prefix="/backtest/optionvault", tags=["OptionVault Walk Forward"])


class OptionVaultWalkForwardRequest(BaseModel):
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
    min_oos_trades: int = Field(default=1, ge=0)
    min_oos_profit_factor: float = Field(default=1.0, gt=0)
    max_oos_drawdown_pct: float = Field(default=35.0, gt=0)


@router.post("/walkforward")
def walkforward(req: OptionVaultWalkForwardRequest):
    try:
        return run_optionvault_walkforward(**req.model_dump())
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
