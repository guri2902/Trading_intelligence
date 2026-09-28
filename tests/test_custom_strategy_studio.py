from datetime import datetime, timedelta, timezone

from backend.app.strategy_studio.executor import backtest_saved_strategy
from backend.app.strategy_studio.models import (
    StrategyBacktestRequest,
    StrategyCondition,
    StrategyDefinition,
    StrategyRules,
)


def _rows() -> list[dict]:
    rows = []
    price = 100.0
    start = datetime(2026, 1, 5, 9, 15, tzinfo=timezone.utc)
    for i in range(50):
        price += 0.8 if i < 20 else -1.4
        rows.append(
            {
                "timestamp": start + timedelta(minutes=5 * i),
                "open": price - 0.2,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price,
                "volume": 1000,
            }
        )
    return rows


def test_custom_rules_are_executable_and_exit_conditions_work():
    strategy = StrategyDefinition(
        name="Custom Test",
        rules=StrategyRules(
            condition_logic="ALL",
            direction="LONG",
            stop_mode="POINTS",
            stop_value=20,
            target_mode="POINTS",
            target_value=100,
            max_trades_per_day=1,
            entry_conditions=[
                StrategyCondition(field="price", operator="GT", value=100)
            ],
            exit_conditions=[
                StrategyCondition(field="price", operator="LT", value=110)
            ],
        ),
    )
    result = backtest_saved_strategy(
        strategy,
        StrategyBacktestRequest(
            rows=_rows(), initial_capital=10000, quantity=1, slippage_bps=0
        ),
    )

    assert result.metrics.total_trades == 1
    assert result.trades[0].strategy == "Custom Test"
    assert result.trades[0].exit_reason == "CONDITION_EXIT"


def test_empty_engine_strategy_uses_custom_rule_path():
    strategy = StrategyDefinition(
        name="Custom Direction",
        rules=StrategyRules(
            direction="LONG",
            stop_mode="POINTS",
            stop_value=1,
            target_mode="RR",
            target_value=2,
            entry_conditions=[
                StrategyCondition(field="price", operator="GT", value=100)
            ],
        ),
    )
    result = backtest_saved_strategy(
        strategy,
        StrategyBacktestRequest(
            rows=_rows(), initial_capital=10000, quantity=1, slippage_bps=0
        ),
    )
    assert result.metrics.total_trades >= 1
