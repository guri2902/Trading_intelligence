from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Create a tiny package namespace so the patched modules can be imported without
# requiring the entire FastAPI/Upstox application runtime.
pkg = types.ModuleType("drypkg")
pkg.__path__ = [str(ROOT)]
sys.modules["drypkg"] = pkg
ob_pkg = types.ModuleType("drypkg.options_backtest")
ob_pkg.__path__ = [str(ROOT)]
sys.modules["drypkg.options_backtest"] = ob_pkg

@dataclass
class Cfg:
    initial_capital: float = 100000.0
    slippage_bps: float = 2.0
    brokerage_per_order: float = 20.0
    def model_copy(self, update=None):
        return replace(self, **(update or {}))

models = types.ModuleType("drypkg.options_backtest.models")
models.OptionsBacktestConfig = Cfg
sys.modules[models.__name__] = models

calls = []

def fake_backtest(rows, **kwargs):
    calls.append(kwargs)
    # 20 strategy-level trades spread across the latter part of the sample.
    base = rows[160]["timestamp"]
    groups = []
    for i in range(20):
        ts = base + timedelta(minutes=5 * i)
        pnl = 150.0 if i % 3 else -80.0
        groups.append({
            "strategy_trade_id": ts.isoformat(),
            "entry_time": ts,
            "exit_time": ts + timedelta(minutes=5),
            "net_pnl": pnl,
            "leg_transactions": 2,
        })
    return {
        "trades": [{"entry_time": g["entry_time"], "net_pnl": g["net_pnl"]} for g in groups for _ in range(2)],
        "strategy_trade_groups": groups,
        "diagnostics": {"multi_leg": bool(kwargs.get("legs"))},
        "warnings": [],
    }

bridge = types.ModuleType("drypkg.options_backtest.strategy_option_bridge")
bridge.run_strategy_option_backtest = fake_backtest
bridge.normalize_rows = lambda rows: sorted([{**r, "timestamp": r["timestamp"]} for r in rows], key=lambda x: x["timestamp"])
sys.modules[bridge.__name__] = bridge

def load(name, filename):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(f"drypkg.options_backtest.{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

wf = load("walkforward", "walkforward.py")
rb = load("robustness", "robustness.py")

rows = [
    {"timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=5 * i), "close": 100 + i * 0.1}
    for i in range(260)
]
legs = [
    {"action": "BUY", "option_type": "CE", "expiry_mode": "NEAREST", "strike_mode": "ATM", "strike_offset": 0, "lots": 1},
    {"action": "SELL", "option_type": "CE", "expiry_mode": "NEAREST", "strike_mode": "ATM_PLUS", "strike_offset": 1, "lots": 1},
]

wf_result = wf.run_optionvault_walkforward(
    rows,
    strategy_name="TEST_MULTI",
    preferred_strategy="VWAP_PULLBACK",
    strike_reference=100.0,
    config=Cfg(),
    train_size=120,
    validation_size=40,
    oos_size=40,
    step=40,
    legs=legs,
    loader=object(),
)
assert wf_result["strategy_legs"] == 2
assert wf_result["oos_summary"]["oos_trade_count"] > 0
assert calls and all(c.get("legs") == legs for c in calls)
assert wf_result["oos_summary"]["base_trade_count"] == 20
assert 0 < len(wf_result["oos_trade_history"]) <= 20

calls.clear()
rb_result = rb.run_optionvault_robustness(
    rows,
    strategy_name="TEST_MULTI",
    preferred_strategy="VWAP_PULLBACK",
    strike_reference=100.0,
    config=Cfg(),
    train_size=120,
    validation_size=40,
    oos_size=40,
    step=40,
    monte_carlo_simulations=100,
    legs=legs,
    loader=object(),
)
assert rb_result["strategy_legs"] == 2
assert rb_result["monte_carlo"]["status"] == "PASS"
assert calls and all(c.get("legs") == legs for c in calls)

suite_src = (ROOT / "optionvault_research_suite.py").read_text()
bridge_src = (ROOT / "strategy_option_bridge.py").read_text()
assert "SKIPPED_MULTI_LEG" not in suite_src
assert "legs=req.legs" in suite_src
assert "strategy_trade_groups" in bridge_src
assert "entry_time" in bridge_src

print("PASS: patched walk-forward accepts and propagates multi-leg legs")
print("PASS: patched robustness accepts and propagates multi-leg legs")
print("PASS: multi-leg OOS uses strategy-level grouped trades, not per-leg transactions")
print("PASS: Research Suite no longer contains SKIPPED_MULTI_LEG fallback")
print(f"PASS: multi-leg legs observed in dry calls = {len(calls[0]['legs']) if calls else 0}")
