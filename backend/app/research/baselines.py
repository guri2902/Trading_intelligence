from __future__ import annotations

from typing import Callable

from ..backtest.engine import BacktestEngine
from ..backtest.models import BacktestConfig


def run_buy_and_hold(
    rows: list[dict],
    *,
    initial_capital: float = 10000.0,
    quantity: float = 1.0,
):
    engine = BacktestEngine()

    def signal(history):
        if len(history) == 1:
            p = float(history[-1]["close"])
            return {
                "direction": "LONG",
                "entry": p,
                "invalidation": -1e99,
                "target_1": 1e99,
                "target_2": 1e99,
            }
        return None

    return engine.run(
        rows,
        signal,
        strategy_name="BUY_AND_HOLD_BASELINE",
        config=BacktestConfig(
            initial_capital=initial_capital,
            quantity=quantity,
        ),
    )


def run_naive_ema(
    rows: list[dict],
    *,
    fast: int = 10,
    slow: int = 30,
    initial_capital: float = 10000.0,
):
    engine = BacktestEngine()

    def signal(history):
        if len(history) < slow:
            return None

        closes = [float(x["close"]) for x in history]

        def ema(values, period):
            alpha = 2.0 / (period + 1.0)
            prev = sum(values[:period]) / period
            for value in values[period:]:
                prev = alpha * value + (1 - alpha) * prev
            return prev

        ef = ema(closes, fast)
        es = ema(closes, slow)
        price = closes[-1]

        if ef > es:
            return {
                "direction": "LONG",
                "entry": price,
                "invalidation": price * 0.99,
                "target_1": price * 1.02,
                "target_2": price * 1.03,
            }

        if ef < es:
            return {
                "direction": "SHORT",
                "entry": price,
                "invalidation": price * 1.01,
                "target_1": price * 0.98,
                "target_2": price * 0.97,
            }

        return None

    return engine.run(
        rows,
        signal,
        strategy_name=f"NAIVE_EMA_{fast}_{slow}",
        config=BacktestConfig(initial_capital=initial_capital),
    )


def compare_to_baselines(
    strategy_result,
    baseline_results: dict[str, object],
) -> dict:
    strategy_metrics = strategy_result.metrics

    return {
        "strategy": {
            "return_pct": strategy_metrics.return_pct,
            "profit_factor": strategy_metrics.profit_factor,
            "max_drawdown_pct": strategy_metrics.max_drawdown_pct,
            "expectancy": strategy_metrics.expectancy_per_trade,
        },
        "baselines": {
            name: {
                "return_pct": result.metrics.return_pct,
                "profit_factor": result.metrics.profit_factor,
                "max_drawdown_pct": result.metrics.max_drawdown_pct,
                "expectancy": result.metrics.expectancy_per_trade,
            }
            for name, result in baseline_results.items()
        },
    }
