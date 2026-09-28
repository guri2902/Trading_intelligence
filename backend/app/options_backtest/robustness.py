from __future__ import annotations

import math
import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .models import OptionsBacktestConfig
from .strategy_option_bridge import run_strategy_option_backtest, normalize_rows


def _ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        value = v
    else:
        value = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _windows(rows: list[dict], train_size: int, validation_size: int, oos_size: int, step: int, expanding: bool):
    cursor = 0
    index = 0
    while True:
        train_start = 0 if expanding else cursor
        train_end = (train_size + cursor) if expanding else (train_start + train_size)
        val_start = train_end
        val_end = val_start + validation_size
        oos_start = val_end
        oos_end = oos_start + oos_size
        if oos_end > len(rows):
            break
        yield index, (train_start, train_end, val_start, val_end, oos_start, oos_end)
        index += 1
        cursor += step
        if cursor >= len(rows):
            break


def _pnl_stats(pnls: list[float]):
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {"net_pnl": equity, "max_drawdown": max_dd}


def _quantile(values: list[float], q: float):
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def monte_carlo_trade_bootstrap(pnls: list[float], *, simulations: int = 2000, seed: int = 42, minimum_trades: int = 10) -> dict[str, Any]:
    clean = [float(x) for x in pnls if x is not None and math.isfinite(float(x))]
    if len(clean) < minimum_trades:
        return {
            "status": "SKIPPED",
            "reason": f"INSUFFICIENT_TRADES:{len(clean)}<{minimum_trades}",
            "trade_count": len(clean),
        }
    sims = max(100, min(int(simulations), 20000))
    rng = random.Random(seed)
    finals, drawdowns = [], []
    for _ in range(sims):
        sample = [clean[rng.randrange(len(clean))] for _ in clean]
        stats = _pnl_stats(sample)
        finals.append(stats["net_pnl"])
        drawdowns.append(stats["max_drawdown"])
    return {
        "status": "PASS",
        "trade_count": len(clean),
        "simulations": sims,
        "seed": seed,
        "observed_net_pnl": sum(clean),
        "median_final_pnl": _quantile(finals, 0.50),
        "p05_final_pnl": _quantile(finals, 0.05),
        "p95_final_pnl": _quantile(finals, 0.95),
        "probability_of_loss_pct": sum(1 for x in finals if x < 0) / len(finals) * 100.0,
        "median_max_drawdown": _quantile(drawdowns, 0.50),
        "p95_max_drawdown": _quantile(drawdowns, 0.95),
    }


def _updated_config(base: OptionsBacktestConfig, *, slippage_multiplier: float, brokerage_multiplier: float):
    updates = {
        "slippage_bps": float(base.slippage_bps) * slippage_multiplier,
        "brokerage_per_order": float(base.brokerage_per_order) * brokerage_multiplier,
    }
    if hasattr(base, "model_copy"):
        return base.model_copy(update=updates)
    cfg = deepcopy(base)
    for k, v in updates.items():
        setattr(cfg, k, v)
    return cfg


def run_optionvault_robustness(
    underlying_rows: list[dict],
    *,
    strategy_name: str,
    preferred_strategy: str,
    strike_reference: float,
    expiry: str | None = None,
    strike_mode: str = "ATM",
    strike_offset: int = 0,
    stop_pct: float = 0.15,
    target_rr: float = 1.5,
    config: OptionsBacktestConfig | None = None,
    train_size: int = 120,
    validation_size: int = 40,
    oos_size: int = 40,
    step: int = 40,
    expanding: bool = True,
    monte_carlo_simulations: int = 2000,
    monte_carlo_seed: int = 42,
    slippage_multipliers: list[float] | None = None,
    brokerage_multipliers: list[float] | None = None,
    legs: list[dict[str, Any]] | None = None,
    loader: Any | None = None,
    base_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = normalize_rows(underlying_rows)
    if len(rows) < train_size + validation_size + oos_size:
        raise ValueError("ROBUSTNESS_HISTORY_TOO_SHORT")

    base_cfg = config or OptionsBacktestConfig()
    provided_base_result = base_result is not None
    slip_mults = slippage_multipliers or [0.5, 1.0, 1.5]
    broker_mults = brokerage_multipliers or [0.5, 1.0, 1.5]

    # Build OOS intervals once. No repeated Upstox calls per window.
    oos_intervals = []
    for window_index, (_, _, _, _, oos_start, oos_end) in _windows(rows, train_size, validation_size, oos_size, step, expanding):
        oos_intervals.append((window_index, _ts(rows[oos_start]["timestamp"]), _ts(rows[oos_end - 1]["timestamp"])))

    def oos_pnls_from_trades(trades: list[dict[str, Any]]) -> list[float]:
        out = []
        for t in trades:
            if t.get("entry_time") is None or t.get("net_pnl") is None:
                continue
            entry = _ts(t["entry_time"])
            if any(start <= entry <= end for _, start, end in oos_intervals):
                out.append(float(t["net_pnl"]))
        return out

    failures: list[dict[str, Any]] = []

    def run_scenario(cfg: OptionsBacktestConfig):
        try:
            return run_strategy_option_backtest(
                rows,
                strategy_name=strategy_name,
                preferred_strategy=preferred_strategy,
                strike_reference=strike_reference,
                expiry=expiry,
                strike_mode=strike_mode,
                strike_offset=strike_offset,
                stop_pct=stop_pct,
                target_rr=target_rr,
                config=cfg,
                loader=loader,
                legs=legs,
            )
        except Exception as exc:
            return {
                "error": f"{type(exc).__name__}: {exc}",
                "trades": [],
            }

    base_result = base_result or run_scenario(base_cfg)
    if base_result.get("error"):
        failures.append({"scope": "BASE", "reason": base_result["error"]})

    base_trades = list(base_result.get("strategy_trade_groups") or base_result.get("trades") or [])
    oos_pnls = oos_pnls_from_trades(base_trades)

    mc = monte_carlo_trade_bootstrap(
        oos_pnls,
        simulations=monte_carlo_simulations,
        seed=monte_carlo_seed,
        minimum_trades=10,
    )

    sensitivity: list[dict[str, Any]] = []
    for sm in slip_mults:
        for bm in broker_mults:
            cfg = _updated_config(base_cfg, slippage_multiplier=float(sm), brokerage_multiplier=float(bm))
            if float(sm) == 1.0 and float(bm) == 1.0 and provided_base_result:
                result = base_result
            else:
                result = run_scenario(cfg)
            if result.get("error"):
                scenario_pnls: list[float] = []
                scenario_failures = [{"scope": "FULL_RUN", "reason": result["error"]}]
            else:
                scenario_pnls = oos_pnls_from_trades(list(result.get("strategy_trade_groups") or result.get("trades") or []))
                scenario_failures = []

            stats = _pnl_stats(scenario_pnls) if scenario_pnls else {"net_pnl": None, "max_drawdown": None}
            sensitivity.append({
                "slippage_multiplier": float(sm),
                "brokerage_multiplier": float(bm),
                "slippage_bps": float(base_cfg.slippage_bps) * float(sm),
                "brokerage_per_order": float(base_cfg.brokerage_per_order) * float(bm),
                "trades": len(scenario_pnls),
                "net_pnl": stats["net_pnl"],
                "max_drawdown": stats["max_drawdown"],
                "failed_windows": scenario_failures,
            })

    base = next((x for x in sensitivity if x["slippage_multiplier"] == 1.0 and x["brokerage_multiplier"] == 1.0), None)
    valid = [x for x in sensitivity if x["net_pnl"] is not None]
    worst = min(valid, key=lambda x: x["net_pnl"], default=None)

    return {
        "strategy": strategy_name,
        "strategy_legs": len(legs or []),
        "data_source": "Upstox",
        "used_actual_option_prices": True,
        "synthetic_prices": False,
        "monte_carlo": mc,
        "failed_windows": failures,
        "cost_slippage_sensitivity": {
            "baseline": base,
            "worst_scenario": worst,
            "scenarios": sensitivity,
        },
    }
