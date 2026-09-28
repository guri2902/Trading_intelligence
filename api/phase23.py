
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from optimization.engine import OptimizationObjective, StrategyOptimizer

router = APIRouter(prefix="/phase23", tags=["phase23"])


class OptimizationRequest(BaseModel):
    search_space: Dict[str, list]
    n_trials: int = Field(default=20, ge=1, le=1000)
    min_trades: int = Field(default=5, ge=0)
    max_drawdown_pct: float | None = Field(default=None, ge=0)
    mock_metrics: Dict[str, Dict[str, float]] | None = None


@router.get("/health")
def health() -> Dict[str, str]:
    return {"phase": "23", "status": "ok"}


@router.post("/optimize")
def optimize(req: OptimizationRequest) -> Dict[str, Any]:
    if req.mock_metrics is None:
        raise HTTPException(
            status_code=400,
            detail="Phase 23 requires an injected evaluator/backtest adapter; no synthetic market results are generated."
        )

    def evaluator(params):
        key = "|".join(f"{k}={params[k]}" for k in sorted(params))
        if key not in req.mock_metrics:
            raise ValueError("No backtest result supplied for sampled parameter set")
        return req.mock_metrics[key]

    optimizer = StrategyOptimizer(
        evaluator=evaluator,
        search_space=req.search_space,
        objective=OptimizationObjective(
            min_trades=req.min_trades,
            max_drawdown_pct=req.max_drawdown_pct,
        ),
    )
    report = optimizer.run(req.n_trials)
    best = None if report.best is None else {
        "trial_number": report.best.trial_number,
        "params": report.best.params,
        "objective": report.best.objective,
        "metrics": report.best.metrics,
    }
    return {
        "best": best,
        "trials": [r.__dict__ for r in report.trials],
    }
