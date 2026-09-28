from datetime import datetime, timedelta, timezone

import pytest

from backend.app.options_backtest.engine import HistoricalOptionsBacktestEngine
from backend.app.options_backtest.models import HistoricalOptionBar, OptionsBacktestConfig


def bar(ts, contract="NIFTY-25000-CE", close=100.0, option_type="CE", bid=None, ask=None):
    return HistoricalOptionBar(
        timestamp=ts,
        contract_key=contract,
        underlying_symbol="NIFTY",
        expiry="2026-09-17",
        strike=25000,
        option_type=option_type,
        open=close,
        high=close + 2,
        low=max(0.1, close - 2),
        close=close,
        bid=bid,
        ask=ask,
    )


def test_actual_option_prices_required_and_used():
    t0 = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    rows = [bar(t0, close=100), bar(t0 + timedelta(minutes=5), close=120), bar(t0 + timedelta(minutes=10), close=130)]
    engine = HistoricalOptionsBacktestEngine()
    result = engine.run(rows, lambda ctx: {"action": "BUY", "contract_key": "NIFTY-25000-CE"}, strategy_name="TEST", config=OptionsBacktestConfig(brokerage_per_order=0, slippage_bps=0))
    assert result.used_actual_option_prices is True
    assert result.trades
    assert result.trades[0].entry_price == 120


def test_no_lookahead_execution():
    t0 = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    rows = [bar(t0, close=100), bar(t0 + timedelta(minutes=5), close=110)]
    result = HistoricalOptionsBacktestEngine().run(rows, lambda ctx: {"action": "BUY", "contract_key": "NIFTY-25000-CE"}, strategy_name="TEST", config=OptionsBacktestConfig(latency_bars=1))
    assert result.no_lookahead is True
    assert result.trades[0].entry_time > t0


def test_duplicate_bar_rejected():
    t0 = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    rows = [bar(t0), bar(t0)]
    with pytest.raises(ValueError, match="DUPLICATE_OPTION_BAR"):
        HistoricalOptionsBacktestEngine().run(rows, lambda _: None, strategy_name="TEST")


def test_crossed_bid_ask_rejected():
    t0 = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    rows = [bar(t0, bid=101, ask=100), bar(t0 + timedelta(minutes=5))]
    with pytest.raises(ValueError, match="BID_ASK_CROSSED"):
        HistoricalOptionsBacktestEngine().run(rows, lambda _: None, strategy_name="TEST")


def test_missing_contract_does_not_synthesize_price():
    t0 = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    rows = [bar(t0), bar(t0 + timedelta(minutes=5)), bar(t0 + timedelta(minutes=10))]
    result = HistoricalOptionsBacktestEngine().run(rows, lambda _: {"action": "BUY", "contract_key": "MISSING"}, strategy_name="TEST")
    assert not result.trades
    assert any("NO_EXECUTION_BAR:MISSING" in w for w in result.warnings)
