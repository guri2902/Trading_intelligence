from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.strategies.engine import StrategyEngine
from backend.app.strategies.models import StrategyContext


# Phase 6/7 values from the real NIFTY 5-minute dataset.
features = {
    "price": 23477.8,
    "ema_9": 23445.0618,
    "ema_20": 23416.5727,
    "ema_50": 23423.2206,
    "rsi_14": 68.84495,
    "atr_14": 18.6107,
    "vwap": 23448.2833,
    "return_1": 0.003758,
    "return_5": 0.003642,
    "return_15": 0.002587,
    "momentum_10": 71.2,
    "volatility_20": 0.0009057,
    "vwap_distance": 29.5167,
    "vwap_distance_pct": 0.0012588,
    "day_open": 23446.6,
    "day_high": 23494.95,
    "day_low": 23380.1,
    "relative_volume_20": None,
    "price_vs_vwap": "ABOVE",
}

structure = {
    "trend": "BEARISH",
    "regime": "TREND",
    "retest": True,
    "rejection": False,
    "failed_breakout": False,
    "pullback": False,
    "support_zones": [
        {
            "center": 23409.385,
            "low": 23380.1,
            "high": 23439.7,
            "touches": 10,
        }
    ],
    "resistance_zones": [
        {
            "center": 23447.51818,
            "low": 23428.15,
            "high": 23473.9,
            "touches": 11,
        }
    ],
}

# Phase 8 real-data result from the fresh 182-quote snapshot.
options = {
    "underlying_symbol": "NIFTY",
    "expiry": "2026-09-15",
    "atm_strike": 23350.0,
    "debate": {
        "underlying_symbol": "NIFTY",
        "expiry": "2026-09-15",
        "atm_strike": 23350.0,
        "ce_score": 118.32,
        "pe_score": 118.36,
        "winner": "PE",
        "reason": "PE has the stronger liquidity/data/contract-quality profile.",
    },
    "best_ce": {
        "contract": {
            "strike": 23350.0,
            "option_type": "CE",
        }
    },
    "best_pe": {
        "contract": {
            "strike": 23350.0,
            "option_type": "PE",
        }
    },
}

# Minimal candles sufficient for strategy evaluation.
# ORB/ORB_RETEST use opening bars, so provide representative
# 5-minute bars from the real NIFTY session.
candles = [
    {
        "timestamp": "2026-09-10T09:15:00+05:30",
        "open": 23446.6,
        "high": 23462.0,
        "low": 23431.35,
        "close": 23455.0,
    },
    {
        "timestamp": "2026-09-10T09:20:00+05:30",
        "open": 23455.0,
        "high": 23470.0,
        "low": 23442.0,
        "close": 23460.0,
    },
    {
        "timestamp": "2026-09-10T09:25:00+05:30",
        "open": 23460.0,
        "high": 23474.0,
        "low": 23450.0,
        "close": 23458.0,
    },
    {
        "timestamp": "2026-09-10T09:30:00+05:30",
        "open": 23458.0,
        "high": 23480.0,
        "low": 23448.0,
        "close": 23465.0,
    },
    {
        "timestamp": "2026-09-10T09:35:00+05:30",
        "open": 23465.0,
        "high": 23490.0,
        "low": 23455.0,
        "close": 23470.0,
    },
    {
        "timestamp": "2026-09-10T09:40:00+05:30",
        "open": 23470.0,
        "high": 23495.0,
        "low": 23460.0,
        "close": 23477.8,
    },
]

context = StrategyContext(
    timestamp="2026-09-10T15:25:00+05:30",
    candles=candles,
    features=features,
    structure=structure,
    options=options,
    regime="TREND",
)

result = StrategyEngine().evaluate(context)

print("\n========== PHASE 9 REAL-DATA TEST ==========")
print("REGIME:", result.regime)
print("TRIGGERED COUNT:", result.triggered_count)

for setup in result.setups:
    print("\n---", setup.strategy, "---")
    print("STATE:", setup.state)
    print("DIRECTION:", setup.direction)
    print("CONFIDENCE:", setup.confidence)
    print("ENTRY:", setup.entry)
    print("SL:", setup.invalidation)
    print("TP1:", setup.target_1)
    print("TP2:", setup.target_2)
    print("RR:", setup.risk_reward)
    print("EVIDENCE:", setup.evidence)
    print("WAIT FOR:", setup.wait_for)
    print("INVALIDATION:", setup.invalidation_reasons)
    print("METADATA:", setup.metadata)

print("\n========== BEST SETUP ==========")

if result.best_setup:
    print("STRATEGY:", result.best_setup.strategy)
    print("DIRECTION:", result.best_setup.direction)
    print("STATE:", result.best_setup.state)
    print("CONFIDENCE:", result.best_setup.confidence)
    print("RR:", result.best_setup.risk_reward)
else:
    print("NO_TRIGGERED_SETUP")

print("\n=============================================")
