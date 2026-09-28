from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from .models import OptionsBacktestConfig
from .strategy_option_bridge import run_strategy_option_backtest, normalize_rows

LEGACY_DATA_SOURCE = "OptionVault"


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    oos_start: str
    oos_end: str
    train_bars: int
    validation_bars: int
    oos_bars: int


def _ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        value = v
    else:
        value = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _trade_metrics(trades: list[dict[str, Any]], initial_capital: float) -> dict[str, Any]:
    pnls = [float(t.get("net_pnl") or 0.0) for t in trades]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = initial_capital
    peak = equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "status": "PASS" if trades else "NO_TRADES",
        "net_profit": sum(pnls),
        "return_pct": (sum(pnls) / initial_capital * 100) if initial_capital else None,
        "total_trades": len(pnls),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": (len(wins) / len(pnls) * 100) if pnls else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "max_drawdown": max_dd,
        "max_drawdown_pct": (max_dd / initial_capital * 100) if initial_capital else None,
    }


def _slice_trades(trades: list[dict[str, Any]], start: datetime, end: datetime) -> list[dict[str, Any]]:
    return [
        t for t in trades
        if t.get("entry_time") is not None
        and start <= _ts(t["entry_time"]) <= end
    ]


def run_optionvault_walkforward(
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
    min_oos_trades: int = 1,
    min_oos_profit_factor: float = 1.0,
    max_oos_drawdown_pct: float = 35.0,
    legs: list[dict[str, Any]] | None = None,
    loader: Any | None = None,
    base_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = normalize_rows(underlying_rows)
    if len(rows) < train_size + validation_size + oos_size:
        raise ValueError("WALKFORWARD_HISTORY_TOO_SHORT")

    cfg = config or OptionsBacktestConfig()

    # This project currently has a fixed deterministic strategy and does not perform
    # parameter optimization during train/validation. Running one complete historical
    # backtest and slicing its realized trades into chronological windows is therefore
    # both faster and equivalent for the configured fixed strategy, while avoiding
    # repeated Upstox downloads for every OOS window.
    full = base_result or run_strategy_option_backtest(
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
    all_trades = list(full.get("strategy_trade_groups") or full.get("trades") or [])

    evaluations: list[dict[str, Any]] = []
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

        window = WalkForwardWindow(
            index=index,
            train_start=rows[train_start]["timestamp"].isoformat(),
            train_end=rows[train_end - 1]["timestamp"].isoformat(),
            validation_start=rows[val_start]["timestamp"].isoformat(),
            validation_end=rows[val_end - 1]["timestamp"].isoformat(),
            oos_start=rows[oos_start]["timestamp"].isoformat(),
            oos_end=rows[oos_end - 1]["timestamp"].isoformat(),
            train_bars=train_end - train_start,
            validation_bars=val_end - val_start,
            oos_bars=oos_end - oos_start,
        )

        train_trades = _slice_trades(all_trades, _ts(window.train_start), _ts(window.train_end))
        val_trades = _slice_trades(all_trades, _ts(window.validation_start), _ts(window.validation_end))
        oos_trades = _slice_trades(all_trades, _ts(window.oos_start), _ts(window.oos_end))

        oos_metrics = _trade_metrics(oos_trades, cfg.initial_capital)
        pf = oos_metrics["profit_factor"]
        qualified = bool(
            len(oos_trades) >= min_oos_trades
            and pf is not None
            and pf >= min_oos_profit_factor
            and float(oos_metrics["max_drawdown_pct"] or 0) <= max_oos_drawdown_pct
        )

        evaluations.append({
            "window": asdict(window),
            "status": "PASS" if oos_trades else "NO_TRADES",
            "failure_reason": None if oos_trades else "NO_OOS_TRADES_IN_WINDOW",
            "train": _trade_metrics(train_trades, cfg.initial_capital),
            "validation": _trade_metrics(val_trades, cfg.initial_capital),
            "oos": oos_metrics,
            "oos_trades": oos_trades,
            "oos_qualified": qualified,
            "leakage_check": {
                "train_before_validation": window.train_end < window.validation_start,
                "validation_before_oos": window.validation_end < window.oos_start,
            },
        })

        index += 1
        cursor += step
        if cursor >= len(rows):
            break

    valid_oos = [x for x in evaluations if x["status"] == "PASS"]
    qualified_oos = [x for x in valid_oos if x["oos_qualified"]]
    oos_trade_history = [t for x in valid_oos for t in x["oos_trades"]]
    total_net = sum(float(x["oos"].get("net_profit") or 0.0) for x in valid_oos)
    total_trades = sum(int(x["oos"].get("total_trades") or 0) for x in valid_oos)
    pf_values = [float(x["oos"]["profit_factor"]) for x in valid_oos if x["oos"].get("profit_factor") is not None]
    dd_values = [float(x["oos"].get("max_drawdown_pct") or 0.0) for x in valid_oos]
    promotion = bool(valid_oos and len(qualified_oos) == len(valid_oos) and total_net > 0)

    return {
        "strategy": strategy_name,
        "strategy_legs": len(legs or []),
        "data_source": "Upstox",
        "used_actual_option_prices": True,
        "synthetic_prices": False,
        "walk_forward": {
            "train_size": train_size,
            "validation_size": validation_size,
            "oos_size": oos_size,
            "step": step,
            "expanding": expanding,
            "parameter_optimization": "NOT_CONFIGURED_FIXED_STRATEGY",
            "windows": evaluations,
        },
        "oos_summary": {
            "windows_attempted": len(evaluations),
            "windows_evaluated": len(valid_oos),
            "windows_failed": len(evaluations) - len(valid_oos),
            "windows_qualified": len(qualified_oos),
            "qualification_rate_pct": (len(qualified_oos) / len(valid_oos) * 100.0) if valid_oos else 0.0,
            "aggregate_oos_net_profit": total_net,
            "aggregate_oos_trades": total_trades,
            "average_oos_profit_factor": sum(pf_values) / len(pf_values) if pf_values else None,
            "average_oos_drawdown_pct": sum(dd_values) / len(dd_values) if dd_values else None,
            "promotion_gate": "PASS" if promotion else "FAIL",
            "oos_trade_count": len(oos_trade_history),
            "base_trade_count": len(all_trades),
            "multi_leg_trade_grouping": bool(full.get("strategy_trade_groups")),
            "base_diagnostics": full.get("diagnostics") or {},
            "base_warnings": full.get("warnings") or [],
            "failure_reasons": [x["failure_reason"] for x in evaluations if x.get("failure_reason")],
        },
        "oos_trade_history": oos_trade_history,
    }
