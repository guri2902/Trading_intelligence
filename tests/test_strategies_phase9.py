from datetime import datetime, timedelta, timezone

from backend.app.strategies.models import StrategyContext
from backend.app.strategies.engine import StrategyEngine


def candles():
    start = datetime(2026, 9, 10, 9, 15, tzinfo=timezone.utc)
    out = []
    for i in range(20):
        price = 100 + i * 0.5
        out.append({
            "timestamp": start + timedelta(minutes=i),
            "open": price,
            "high": price + 1,
            "low": price - 0.4,
            "close": price + 0.7,
            "volume": 1500,
        })
    return out


def features():
    return {
        "price": 110,
        "vwap": 108,
        "atr_14": 2,
        "ema_9": 109,
        "ema_20": 107,
        "ema_50": 104,
        "rsi_14": 61,
        "relative_volume_20": 1.4,
        "momentum_10": 4,
        "price_vs_vwap": "ABOVE",
        "day_high": 110,
        "day_low": 99,
        "day_open": 100,
        "pdh": 109,
        "pdl": 98,
        "pdc": 100,
    }


def structure():
    return {
        "trend": "BULLISH",
        "regime": "BREAKOUT",
        "support_zones": [{"center": 106, "low": 105.5, "high": 106.5, "touches": 2}],
        "resistance_zones": [{"center": 110, "low": 109.5, "high": 110.5, "touches": 2}],
        "rejection": False,
    }


def test_strategy_engine_returns_all_strategies():
    context = StrategyContext(
        timestamp=candles()[-1]["timestamp"],
        candles=candles(),
        features=features(),
        structure=structure(),
    )
    result = StrategyEngine().evaluate(context)
    assert len(result.setups) == 9
    assert result.triggered_count >= 1
    assert result.best_setup is not None


def test_no_forced_trade_in_neutral_context():
    f = features()
    f.update({
        "ema_9": 105,
        "ema_20": 105,
        "ema_50": 105,
        "rsi_14": 50,
        "relative_volume_20": 0.7,
        "momentum_10": 0,
        "price_vs_vwap": "AT_VWAP",
        "vwap": 110,
    })
    context = StrategyContext(
        timestamp=candles()[-1]["timestamp"],
        candles=candles(),
        features=f,
        structure={
            "trend": "RANGE",
            "regime": "CONSOLIDATION",
            "support_zones": [],
            "resistance_zones": [],
            "rejection": False,
        },
    )
    result = StrategyEngine().evaluate(context)
    assert result.triggered_count == 0


def test_rr_is_positive_for_triggered_setup():
    context = StrategyContext(
        timestamp=candles()[-1]["timestamp"],
        candles=candles(),
        features=features(),
        structure=structure(),
    )
    result = StrategyEngine().evaluate(context)
    triggered = [x for x in result.setups if x.state == "TRIGGERED"]
    assert all(x.risk_reward is None or x.risk_reward > 0 for x in triggered)
