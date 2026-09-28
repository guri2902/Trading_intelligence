from datetime import datetime, timezone
from backend.app.paper.execution import CostConfig, MarketQuote, RealisticExecutionSimulator


def test_buy_prefers_ask_and_slips_up():
    s = RealisticExecutionSimulator(CostConfig(base_slippage_bps=10))
    f = s.fill("BUY", 50, MarketQuote(100, bid=99, ask=101))
    assert f.filled_qty == 50
    assert f.fill_price > 101
    assert f.slippage_cost > 0


def test_partial_fill_respects_liquidity():
    s = RealisticExecutionSimulator()
    f = s.fill("SELL", 100, MarketQuote(100, bid=99.5, ask=100.5, available_qty=40))
    assert f.filled_qty == 40
    assert f.partial is True


def test_costs_are_positive_and_sell_stt_applies():
    s = RealisticExecutionSimulator()
    c1 = s.costs(5000, 5500, 2)
    c2 = s.costs(5000, 0, 1)
    assert c1.total > c2.total
    assert c1.stt > 0
    assert c1.gst > 0


def test_expiry_intrinsic_value():
    s = RealisticExecutionSimulator()
    assert s.expiry_value("CE", 25000, 25120) == 120
    assert s.expiry_value("PE", 25000, 24880) == 120


def test_expiry_date_detection():
    s = RealisticExecutionSimulator()
    ts = datetime(2026, 9, 17, 10, tzinfo=timezone.utc)
    assert s.is_expired("2026-09-17", ts) is True
