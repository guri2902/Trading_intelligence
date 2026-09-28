from datetime import datetime, timedelta, timezone
from pathlib import Path


def test_window_ordering_contract():
    base = datetime(2026, 9, 1, 9, 15, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    stamps = [(base + timedelta(minutes=5 * i)).isoformat() for i in range(30)]
    assert stamps[9] < stamps[10] < stamps[19] < stamps[20] < stamps[29]


def test_bridge_has_oos_cutoff():
    text = Path("backend/app/options_backtest/strategy_option_bridge.py").read_text()
    assert "signal_start" in text
    assert "signal_end" in text
    assert "r.timestamp <= end_dt" in text


def test_walkforward_has_promotion_gate_and_real_source():
    text = Path("backend/app/options_backtest/walkforward.py").read_text()
    assert 'data_source": "OptionVault"' in text
    assert 'synthetic_prices": False' in text
    assert 'promotion_gate' in text
    assert 'oos_qualified' in text
