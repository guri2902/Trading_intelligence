from __future__ import annotations

import argparse
from pathlib import Path

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..backtest.engine import BacktestEngine
from ..backtest.models import BacktestConfig
from ..backtest.strategy_adapter import StrategyBacktestAdapter
from ..research.promotion import evaluate_promotion
from ..research.walk_forward import walk_forward_splits, summarize_splits
from ..strategies.models import StrategyContext
from ..features.service import FeatureService
from ..structure.service import StructureService

router = APIRouter(prefix="/phase11", tags=["phase11"])


class WalkForwardRequest(BaseModel):
    row_count: int = Field(..., ge=1)
    train_size: int = Field(..., gt=0)
    validation_size: int = Field(..., gt=0)
    test_size: int = Field(..., gt=0)
    step: int | None = Field(default=None, gt=0)
    expanding: bool = True


class PromotionRequest(BaseModel):
    in_sample_score: float
    validation_score: float
    oos_score: float
    robustness_pass: bool = False
    baseline_outperformance: bool = False
    paper_validation_pass: bool = False


class WalkForwardRunRequest(BaseModel):
    rows: list[dict]
    strategy: str = "ALL"

    train_size: int = Field(..., gt=0)
    validation_size: int = Field(..., gt=0)
    test_size: int = Field(..., gt=0)
    step: int | None = Field(default=None, gt=0)
    expanding: bool = True

    config: BacktestConfig = BacktestConfig()

    baseline_score: float = 0.0
    robustness_pass: bool = False
    paper_validation_pass: bool = False


def _normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []

    for row in rows:
        item = dict(row)
        ts = item.get("timestamp")

        if ts is None:
            raise ValueError("Every row must contain timestamp")

        if isinstance(ts, str):
            item["timestamp"] = datetime.fromisoformat(
                ts.replace("Z", "+00:00")
            )

        normalized.append(item)

    normalized.sort(
        key=lambda x: x["timestamp"]
    )

    return normalized


def _build_context(history: list[dict]) -> StrategyContext:
    features = FeatureService().calculate(
        history,
        session_ids=None,
    )

    structure = StructureService().analyze(history)

    return StrategyContext(
        timestamp=history[-1]["timestamp"],
        candles=history,
        features=features,
        structure=structure,
        options=None,
        regime=structure.get("regime"),
    )


def _backtest(
    rows: list[dict],
    strategy: str,
    config: BacktestConfig,
    *,
    trade_start_index: int = 0,
):
    if len(rows) < 15:
        return None

    preferred = (
        None
        if strategy.upper() in {"ALL", "BEST"}
        else strategy
    )

    adapter = StrategyBacktestAdapter(
        state_fn=_build_context,
        preferred_strategy=preferred,
    )

    def signal_fn(history):
        if len(history) < 15:
            return None
        return adapter.signal(history)

    return BacktestEngine().run(
        rows,
        signal_fn,
        strategy_name=strategy,
        config=config,
        mode="UNDERLYING",
        trade_start_index=trade_start_index,
    )


def _score(result) -> float:
    if result is None:
        return 0.0

    metrics = result.metrics

    # Deterministic walk-forward score:
    # net profit penalized by drawdown.
    drawdown = max(metrics.max_drawdown, 0.0)

    return float(
        metrics.net_profit
        - 0.50 * drawdown
    )


@router.post("/walk-forward/plan")
def plan_walk_forward(request: WalkForwardRequest):
    rows = list(range(request.row_count))

    splits = walk_forward_splits(
        rows,
        train_size=request.train_size,
        validation_size=request.validation_size,
        test_size=request.test_size,
        step=request.step,
        expanding=request.expanding,
    )

    return summarize_splits(splits)


@router.post("/promotion-gate")
def promotion_gate(request: PromotionRequest):
    return evaluate_promotion(
        in_sample_score=request.in_sample_score,
        validation_score=request.validation_score,
        oos_score=request.oos_score,
        robustness_pass=request.robustness_pass,
        baseline_outperformance=request.baseline_outperformance,
        paper_validation_pass=request.paper_validation_pass,
    )


@router.post("/run")
def run_walk_forward(request: WalkForwardRunRequest):
    try:
        rows = _normalize_rows(request.rows)

        if len(rows) < (
            request.train_size
            + request.validation_size
            + request.test_size
        ):
            raise HTTPException(
                400,
                "Not enough rows for the requested walk-forward configuration.",
            )

        splits = walk_forward_splits(
            rows,
            train_size=request.train_size,
            validation_size=request.validation_size,
            test_size=request.test_size,
            step=request.step,
            expanding=request.expanding,
        )

        if not splits:
            raise HTTPException(
                400,
                "No valid walk-forward splits were produced.",
            )

        split_results = []

        for split in splits:

            train_result = _backtest(
                split.train,
                request.strategy,
                request.config,
                trade_start_index=0,
            )
            validation_rows = split.train + split.validation

            validation_result = _backtest(
                validation_rows,
                request.strategy,
                request.config,
                trade_start_index=len(split.train),
            )
            oos_rows = split.train + split.validation + split.test
            oos_result = _backtest(
                oos_rows,
                request.strategy,
                request.config,
                trade_start_index=(
                    len(split.train)
                    + len(split.validation)
                ),
            )

            train_score = _score(train_result)
            validation_score = _score(validation_result)
            oos_score = _score(oos_result)

            split_results.append(
                {
                    "split_id": split.split_id,
                    "train": {
                        "rows": len(split.train),
                        "score": train_score,
                        "metrics": (
                            train_result.metrics.model_dump(mode="json")
                            if train_result
                            else None
                        ),
                    },
                    "validation": {
                        "rows": len(split.validation),
                        "score": validation_score,
                        "metrics": (
                            validation_result.metrics.model_dump(mode="json")
                            if validation_result
                            else None
                        ),
                    },
                    "oos": {
                        "rows": len(split.test),
                        "score": oos_score,
                        "metrics": (
                            oos_result.metrics.model_dump(mode="json")
                            if oos_result
                            else None
                        ),
                    },
                }
            )

        train_scores = [
            x["train"]["score"]
            for x in split_results
        ]

        validation_scores = [
            x["validation"]["score"]
            for x in split_results
        ]

        oos_scores = [
            x["oos"]["score"]
            for x in split_results
        ]

        in_sample_score = (
            sum(train_scores) / len(train_scores)
            if train_scores
            else 0.0
        )

        validation_score = (
            sum(validation_scores) / len(validation_scores)
            if validation_scores
            else 0.0
        )

        oos_score = (
            sum(oos_scores) / len(oos_scores)
            if oos_scores
            else 0.0
        )

        baseline_outperformance = (
            oos_score > request.baseline_score
        )

        # Conservative robustness rule:
        # at least half of OOS splits must be positive.
        positive_oos = sum(
            score > 0
            for score in oos_scores
        )

        robustness_pass = (
            positive_oos >= max(
                1,
                len(oos_scores) // 2 + len(oos_scores) % 2,
            )
        ) and request.robustness_pass

        gate = evaluate_promotion(
            in_sample_score=in_sample_score,
            validation_score=validation_score,
            oos_score=oos_score,
            robustness_pass=robustness_pass,
            baseline_outperformance=baseline_outperformance,
            paper_validation_pass=request.paper_validation_pass,
        )

        return {
            "strategy": request.strategy,
            "row_count": len(rows),
            "split_count": len(split_results),
            "aggregate": {
                "in_sample_score": in_sample_score,
                "validation_score": validation_score,
                "oos_score": oos_score,
                "baseline_score": request.baseline_score,
                "positive_oos_splits": positive_oos,
            },
            "promotion": {
                "passed": gate.passed,
                "reasons": gate.reasons,
                "checks": gate.checks,
            },
            "splits": split_results,
        }

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(
            500,
            f"Walk-forward execution failed: {exc}",
        )