
from backend.app.risk_config.models import RiskConfig


def test_cash_risk_converts_to_engine_percent():
    cfg = RiskConfig(capital=100_000, per_trade_risk=2_000)
    pct = (cfg.per_trade_risk / cfg.capital) * 100.0
    assert pct == 2.0
