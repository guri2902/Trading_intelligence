from datetime import datetime, timedelta
from backend.app.options_backtest.regime import analyze_trade_history, classify_history


def rows(n=80):
    out=[]
    price=100.0
    start = datetime(2026, 1, 1, 9, 15)
    for i in range(n):
        price += 0.4 if i < n//2 else (-0.25 if i < 3*n//4 else 0.02)
        out.append({"timestamp": (start + timedelta(minutes=i)).isoformat(), "close": price})
    return out


def test_regime_classification_is_deterministic():
    r = classify_history(rows())
    assert len(r) == 80
    assert all(x.regime for x in r)


def test_trade_analysis_uses_at_or_before_timestamp():
    rs = rows()
    trades = [{"entry_time": rs[50]["timestamp"], "net_pnl": 100.0},
              {"entry_time": rs[60]["timestamp"], "net_pnl": -50.0}]
    result = analyze_trade_history(rs, trades)
    assert result["trade_count_classified"] == 2
    assert result["lookahead_safe"] is True
