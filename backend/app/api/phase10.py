from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..backtest.engine import BacktestEngine
from ..backtest.models import BacktestConfig
from ..backtest.strategy_adapter import StrategyBacktestAdapter
from ..features.service import FeatureService
from ..structure.service import StructureService
from ..strategies.models import StrategyContext

router = APIRouter(prefix="/phase10", tags=["phase10"])


class BacktestRequest(BaseModel):
    rows: list[dict]
    strategy: str = "ALL"
    mode: str = "UNDERLYING"
    config: BacktestConfig = BacktestConfig()


class SimpleSignalSpec(BaseModel):
    """
    Minimal API-safe signal generator for deterministic smoke tests.
    """
    direction: str = "LONG"
    entry_offset: float = 0.0
    stop_distance: float = 1.0
    target_distance: float = 2.0


@router.post("/smoke")
def backtest_smoke(
    request: BacktestRequest,
    signal_spec: SimpleSignalSpec,
):
    if len(request.rows) < 3:
        raise HTTPException(400, "At least 3 rows are required")

    engine = BacktestEngine()

    def signal_fn(history):
        current = float(history[-1]["close"])
        d = signal_spec.direction

        if d == "LONG":
            return {
                "direction": "LONG",
                "entry": current + signal_spec.entry_offset,
                "invalidation": current - signal_spec.stop_distance,
                "target_1": current + signal_spec.target_distance,
                "target_2": current + signal_spec.target_distance,
            }

        return {
            "direction": "SHORT",
            "entry": current - signal_spec.entry_offset,
            "invalidation": current + signal_spec.stop_distance,
            "target_1": current - signal_spec.target_distance,
            "target_2": current - signal_spec.target_distance,
        }

    return engine.run(
        request.rows,
        signal_fn,
        strategy_name=request.strategy,
        config=request.config,
        mode=request.mode,
    ).model_dump(mode="json")

def normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []

    for row in rows:
        item = dict(row)
        ts = item.get("timestamp")

        if ts is None:
            raise ValueError("Each historical row must contain timestamp")

        if isinstance(ts, str):
            item["timestamp"] = datetime.fromisoformat(
                ts.replace("Z", "+00:00")
            )

        normalized.append(item)

    return normalized


def build_strategy_context(history: list[dict]):
    """
    Build Phase 9 state exclusively from bars available at the
    current historical decision point.

    No future candle is passed to the strategy.
    """
    feature_service = FeatureService()
    structure_service = StructureService()

    features = feature_service.calculate(
        history,
        session_ids=None,
    )

    structure = structure_service.analyze(history)

    return {
        "timestamp": history[-1]["timestamp"],
        "candles": history,
        "features": features,
        "structure": structure,
        "options": None,
        "regime": structure.get("regime"),
    }


@router.post("/strategy")
def backtest_strategy(request: BacktestRequest):
    rows = normalize_rows(request.rows)
    if request.mode != "UNDERLYING":
        raise HTTPException(
            400,
            "Phase 10 strategy endpoint currently supports UNDERLYING mode only. "
            "Use historical option data for an OPTIONS backtest.",
        )

    if len(rows) < 15:
        raise HTTPException(
            400,
            "At least 15 historical candles are required for strategy backtesting.",
        )

    if request.strategy.upper() not in {
        "ALL",
        "BEST",
        "VWAP_PULLBACK",
        "EMA_CONTINUATION",
        "ORB",
        "ORB_RETEST",
        "SR_REJECTION",
        "RANGE_FADE",
        "MOMENTUM_CONTINUATION",
        "VOLATILITY_BREAKOUT",
    }:
        raise HTTPException(
            400,
            f"Unsupported underlying strategy: {request.strategy}",
        )

    try:
        preferred_strategy = (
            None
            if request.strategy.upper() in {"ALL", "BEST"}
            else request.strategy
        )

        adapter = StrategyBacktestAdapter(
            state_fn=lambda history: StrategyContext(
                **build_strategy_context(history)
            ),
            preferred_strategy=preferred_strategy,
        )

        def signal_fn(history):
            # Phase 6/7 need sufficient history before a strategy
            # decision can be made.
            if len(history) < 15:
                return None

            return adapter.signal(history)

        engine = BacktestEngine()

        return engine.run(
            rows,
            signal_fn,
            strategy_name=request.strategy,
            config=request.config,
            mode=request.mode,
        ).model_dump(mode="json")

    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(
            500,
            f"Phase 10 strategy backtest failed: {exc}",
        )