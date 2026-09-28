from __future__ import annotations

import math
from time import perf_counter

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from ..options_backtest.models import OptionsBacktestConfig
from ..options_backtest.strategy_option_bridge import run_strategy_option_backtest
from ..options_backtest.upstox_loader import UpstoxHistoricalOptionLoader
from ..options_backtest.walkforward import run_optionvault_walkforward
from ..options_backtest.robustness import run_optionvault_robustness
from ..options_backtest.regime import analyze_trade_history
from ..options_backtest.qualification import qualify_optionvault_research
from ..options_backtest.quality import score_optionvault_strategy


router = APIRouter(
    prefix="/backtest/upstox",
    tags=["Upstox Backtest"],
)


class ResearchSuiteRequest(BaseModel):
    underlying_rows: list[dict] = Field(min_length=30)
    strategy_name: str = Field(min_length=1)
    preferred_strategy: str = Field(min_length=1)
    strike_reference: float
    expiry: str | None = None
    strike_mode: str = "ATM"
    strike_offset: int = 0
    stop_pct: float = Field(default=0.15, gt=0)
    target_rr: float = Field(default=1.5, gt=0)

    # Saved Strategy Builder multi-leg definition.
    # Empty = legacy single-leg backtest.
    legs: list[dict] = Field(default_factory=list)

    config: OptionsBacktestConfig = Field(default_factory=OptionsBacktestConfig)
    train_size: int = Field(default=120, gt=0)
    validation_size: int = Field(default=40, gt=0)
    oos_size: int = Field(default=40, gt=0)
    step: int = Field(default=40, gt=0)
    expanding: bool = True
    monte_carlo_simulations: int = Field(default=1000, ge=100, le=20000)
    monte_carlo_seed: int = 42


def _sanitize(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return value


def _safe(value):
    return _sanitize(jsonable_encoder(value))


def _common_kwargs(req: ResearchSuiteRequest) -> dict:
    return {
        "underlying_rows": req.underlying_rows,
        "strategy_name": req.strategy_name,
        "preferred_strategy": req.preferred_strategy,
        "strike_reference": req.strike_reference,
        "expiry": req.expiry,
        "strike_mode": req.strike_mode,
        "strike_offset": req.strike_offset,
        "stop_pct": req.stop_pct,
        "target_rr": req.target_rr,
        "config": req.config,
        "train_size": req.train_size,
        "validation_size": req.validation_size,
        "oos_size": req.oos_size,
        "step": req.step,
        "expanding": req.expanding,
        "legs": req.legs,
    }


@router.post("/research-suite")
def research_suite(req: ResearchSuiteRequest):
    started = perf_counter()

    # One shared loader is used by base/walk-forward/robustness so the
    # expensive Upstox historical contract/bar preparation can be cached.
    loader = UpstoxHistoricalOptionLoader()

    try:
        base_started = perf_counter()
        base = run_strategy_option_backtest(
            underlying_rows=req.underlying_rows,
            strategy_name=req.strategy_name,
            preferred_strategy=req.preferred_strategy,
            strike_reference=req.strike_reference,
            expiry=req.expiry,
            strike_mode=req.strike_mode,
            strike_offset=req.strike_offset,
            stop_pct=req.stop_pct,
            target_rr=req.target_rr,
            config=req.config,
            loader=loader,
            legs=req.legs,
        )
        base_elapsed_ms = round((perf_counter() - base_started) * 1000, 1)

        walk_started = perf_counter()
        walkforward = run_optionvault_walkforward(
            **_common_kwargs(req),
            base_result=base,
            loader=loader,
        )
        walk_elapsed_ms = round((perf_counter() - walk_started) * 1000, 1)

        robustness_started = perf_counter()
        robustness = run_optionvault_robustness(
            **_common_kwargs(req),
            monte_carlo_simulations=req.monte_carlo_simulations,
            monte_carlo_seed=req.monte_carlo_seed,
            base_result=base,
            loader=loader,
        )
        robustness_elapsed_ms = round(
            (perf_counter() - robustness_started) * 1000, 1
        )

        oos_trades = walkforward.get("oos_trade_history") or []
        evidence_sample = "OOS" if oos_trades else "BASE_FALLBACK"
        regime_trades = oos_trades if oos_trades else list(base.get("strategy_trade_groups") or base.get("trades") or [])

        regime_analysis = analyze_trade_history(
            req.underlying_rows,
            regime_trades,
        )

        regime = {
            "data_source": "Upstox",
            "used_actual_option_prices": True,
            "synthetic_prices": False,
            "walk_forward": walkforward.get("walk_forward"),
            "oos_summary": walkforward.get("oos_summary"),
            "regime_analysis": regime_analysis,
            **regime_analysis,
            "evidence_sample": evidence_sample,
            "oos_classified_trades": len(oos_trades),
            "base_classified_trades": (
                len(regime_trades)
                if evidence_sample == "BASE_FALLBACK"
                else 0
            ),
        }

        qualification = qualify_optionvault_research(
            walkforward=walkforward,
            robustness=robustness,
            regime=regime,
        )

        quality = score_optionvault_strategy(
            qualification=qualification,
            walkforward=walkforward,
            robustness=robustness,
            regime=regime,
        )

        total_elapsed_ms = round((perf_counter() - started) * 1000, 1)

        diagnostics = base.get("diagnostics")
        cache_info = (
            diagnostics.get("preparation_cache")
            if isinstance(diagnostics, dict)
            else None
        )

        return _safe(
            {
                "strategy": req.strategy_name,
                "data_source": "Upstox",
                "provider": "Upstox",
                "market": "NIFTY",
                "used_actual_option_prices": True,
                "synthetic_prices": False,
                "strategy_legs": len(req.legs),
                "base_backtest": base,
                "walkforward": walkforward,
                "robustness": robustness,
                "regime": regime,
                "qualification": qualification,
                "quality": quality,
                "performance": {
                    "base_ms": base_elapsed_ms,
                    "walkforward_ms": walk_elapsed_ms,
                    "robustness_ms": robustness_elapsed_ms,
                    "total_ms": total_elapsed_ms,
                    "cache": cache_info,
                },
            }
        )

    except HTTPException:
        raise
    except (
        ValueError,
        FileNotFoundError,
        OSError,
        TypeError,
        KeyError,
        ZeroDivisionError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc
