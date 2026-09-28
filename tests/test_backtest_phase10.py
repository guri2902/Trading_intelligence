from datetime import datetime, timedelta, timezone

from backend.app.backtest.engine import BacktestEngine
from backend.app.backtest.models import BacktestConfig, CostConfig
from backend.app.backtest.costs import apply_slippage


def rows():
    start = datetime(2026, 9, 10, 9, 15, tzinfo=timezone.utc)
    closes = [100, 101, 102, 103, 104, 105, 106, 104, 103]
    result = []
    for i, close in enumerate(closes):
        result.append({
            "timestamp": start + timedelta(minutes=i),
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000,
        })
    return result


def test_slippage_is_directionally_adverse():
    assert apply_slippage(100, "LONG", 10) > 100
    assert apply_slippage(100, "SHORT", 10) < 100


def test_backtest_generates_trades_and_metrics():
    engine = BacktestEngine()

    def signal(history):
        if len(history) in {2, 6}:
            p = history[-1]["close"]
            return {
                "direction": "LONG",
                "entry": p,
                "invalidation": p - 1.5,
                "target_1": p + 2,
                "target_2": p + 2,
            }
        return None

    result = engine.run(
        rows(),
        signal,
        strategy_name="TEST",
        config=BacktestConfig(
            initial_capital=10000,
            quantity=1,
            costs=CostConfig(slippage_bps=2),
        ),
    )

    assert result.metrics.total_trades >= 1
    assert result.metrics.final_equity != 0
    assert result.trades


def test_same_bar_stop_and_target_is_conservative():
    engine = BacktestEngine()

    test_rows = [
        {
            "timestamp": datetime(
                2026, 9, 10, 9, 15,
                tzinfo=timezone.utc,
            ),
            "open": 100,
            "high": 100.5,
            "low": 99.5,
            "close": 100,
        },
        {
            # Entry bar.
            # SL/TP are intentionally both inside this bar,
            # but the engine must NOT exit on the entry bar.
            "timestamp": datetime(
                2026, 9, 10, 9, 16,
                tzinfo=timezone.utc,
            ),
            "open": 100,
            "high": 102,
            "low": 98,
            "close": 100,
        },
        {
            # First eligible exit bar.
            # Both stop and target are hit -> conservative STOP first.
            "timestamp": datetime(
                2026, 9, 10, 9, 17,
                tzinfo=timezone.utc,
            ),
            "open": 100,
            "high": 102,
            "low": 98,
            "close": 100,
        },
    ]

    def signal(history):
        if len(history) == 1:
            return {
                "direction": "LONG",
                "entry": 100,
                "invalidation": 99,
                "target_1": 101,
                "target_2": 101,
            }
        return None

    result = engine.run(
        test_rows,
        signal,
        strategy_name="AMBIGUITY",
        config=BacktestConfig(quantity=1),
    )

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.exit_reason == (
        "STOP_AND_TARGET_SAME_BAR_STOP_FIRST"
    )

    assert trade.entry_time == datetime(
        2026, 9, 10, 9, 16,
        tzinfo=timezone.utc,
    )

    assert trade.exit_time == datetime(
        2026, 9, 10, 9, 17,
        tzinfo=timezone.utc,
    )

    assert trade.duration_bars == 1

def test_options_mode_warns_against_synthetic_option_prices():
    engine = BacktestEngine()

    def no_signal(history):
        return None

    result = engine.run(
        rows(),
        no_signal,
        strategy_name="OPTIONS_TEST",
        mode="OPTIONS",
    )
    assert any("actual historical option prices" in w for w in result.warnings)
