from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..options_backtest.models import OptionsBacktestConfig
from ..options_backtest.robustness import run_optionvault_robustness

router = APIRouter(prefix="/backtest/optionvault", tags=["OptionVault Robustness"])

class OptionVaultRobustnessRequest(BaseModel):
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
    monte_carlo_simulations: int = Field(default=2000, ge=100, le=20000)
    monte_carlo_seed: int = 42
    slippage_multipliers: list[float] = [0.0, 0.5, 1.0, 1.5, 2.0]
    brokerage_multipliers: list[float] = [0.5, 1.0, 1.5, 2.0]

@router.post("/robustness")
def robustness(req: OptionVaultRobustnessRequest):
    try:
        return run_optionvault_robustness(**req.model_dump())
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
