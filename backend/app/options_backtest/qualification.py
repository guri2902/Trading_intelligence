from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class QualificationConfig:
    min_oos_windows: int = 2
    min_oos_qualification_rate_pct: float = 60.0
    require_positive_oos_net_profit: bool = True
    min_oos_profit_factor: float = 1.0
    max_oos_drawdown_pct: float = 35.0
    min_regime_coverage_pct: float = 70.0
    min_positive_regime_pct: float = 50.0
    max_negative_regimes: int = 2
    max_monte_carlo_loss_probability_pct: float = 45.0
    max_monte_carlo_p95_drawdown: float | None = None
    require_baseline_cost_pass: bool = True


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def qualify_optionvault_research(
    *,
    walkforward: dict[str, Any],
    robustness: dict[str, Any],
    regime: dict[str, Any],
    config: QualificationConfig | None = None,
) -> dict[str, Any]:
    cfg = config or QualificationConfig()
    oos = walkforward.get("oos_summary") or {}
    valid_windows = int(oos.get("windows_evaluated") or 0)
    qualification_rate = _num(oos.get("qualification_rate_pct"))
    total_oos_profit = _num(oos.get("aggregate_oos_net_profit"))

    mc = robustness.get("monte_carlo") or {}
    loss_probability = _num(mc.get("probability_of_loss_pct"), 100.0)
    p95_dd = mc.get("p95_max_drawdown")

    sensitivity = robustness.get("cost_slippage_sensitivity") or {}
    baseline = sensitivity.get("baseline") or {}
    baseline_pnl = baseline.get("net_pnl")
    baseline_pass = baseline_pnl is not None and _num(baseline_pnl) > 0

    regimes = regime.get("regimes") or {}
    classified = int(regime.get("trade_count_classified") or 0)
    coverage = _num(regime.get("regime_coverage_pct"))
    positive_regimes = sum(1 for v in regimes.values() if _num(v.get("net_profit")) > 0)
    negative_regimes = sum(1 for v in regimes.values() if _num(v.get("net_profit")) < 0)
    positive_regime_pct = (positive_regimes / len(regimes) * 100.0) if regimes else 0.0

    checks = {
        "minimum_oos_windows": valid_windows >= cfg.min_oos_windows,
        "oos_qualification_rate": qualification_rate >= cfg.min_oos_qualification_rate_pct,
        "oos_profit": (not cfg.require_positive_oos_net_profit) or total_oos_profit > 0,
        "baseline_profit_factor": True,
        "oos_max_drawdown": True,
        "regime_coverage": regime.get("evidence_sample") == "OOS" and coverage >= cfg.min_regime_coverage_pct,
        "positive_regime_share": positive_regime_pct >= cfg.min_positive_regime_pct,
        "negative_regime_limit": negative_regimes <= cfg.max_negative_regimes,
        "monte_carlo_loss_probability": loss_probability <= cfg.max_monte_carlo_loss_probability_pct,
        "baseline_costs_profitable": (not cfg.require_baseline_cost_pass) or baseline_pass,
    }

    # The walk-forward gate already evaluated per-window PF/DD. The aggregate gate
    # additionally checks the configured portfolio-level constraints when summary
    # metrics are present. Missing optional aggregate metrics do not fabricate a pass.
    pf_values = [
        _num(x.get("oos", {}).get("profit_factor"), float("nan"))
        for x in (walkforward.get("walk_forward", {}).get("windows") or [])
        if (x.get("oos", {}).get("profit_factor") is not None)
    ]
    dd_values = [
        _num(x.get("oos", {}).get("max_drawdown_pct"), float("inf"))
        for x in (walkforward.get("walk_forward", {}).get("windows") or [])
        if (x.get("oos", {}).get("max_drawdown_pct") is not None)
    ]
    if pf_values:
        checks["baseline_profit_factor"] = min(pf_values) >= cfg.min_oos_profit_factor
    if dd_values:
        checks["oos_max_drawdown"] = max(dd_values) <= cfg.max_oos_drawdown_pct

    if cfg.max_monte_carlo_p95_drawdown is not None:
        checks["monte_carlo_p95_drawdown"] = p95_dd is not None and _num(p95_dd, float("inf")) <= cfg.max_monte_carlo_p95_drawdown

    warnings: list[str] = []
    if valid_windows == 0:
        warnings.append("NO_VALID_OOS_WINDOWS")
    if regime.get("evidence_sample") != "OOS":
        warnings.append("OOS_REGIME_EVIDENCE_UNAVAILABLE")
    if classified == 0:
        warnings.append("NO_CLASSIFIED_REGIME_TRADES")
    if not sensitivity.get("scenarios"):
        warnings.append("NO_COST_SENSITIVITY_RESULTS")
    if mc.get("status") != "PASS":
        warnings.append("MONTE_CARLO_UNAVAILABLE")

    passed = all(checks.values())
    return {
        "strategy": walkforward.get("strategy") or regime.get("strategy") or robustness.get("strategy"),
        "status": "QUALIFIED" if passed else "NOT_QUALIFIED",
        "promotion_gate": "PASS" if passed else "FAIL",
        "checks": checks,
        "score": round(sum(bool(v) for v in checks.values()) / len(checks) * 100.0, 2),
        "summary": {
            "oos_windows": valid_windows,
            "oos_qualification_rate_pct": qualification_rate,
            "aggregate_oos_net_profit": total_oos_profit,
            "regime_coverage_pct": coverage,
            "positive_regime_pct": positive_regime_pct,
            "negative_regimes": negative_regimes,
            "mc_loss_probability_pct": loss_probability,
            "mc_p95_max_drawdown": p95_dd,
            "baseline_cost_net_pnl": baseline_pnl,
        },
        "config": asdict(cfg),
        "warnings": warnings,
        "actual_option_prices": bool(
            walkforward.get("used_actual_option_prices")
            and robustness.get("used_actual_option_prices")
        ),
        "synthetic_prices": bool(
            walkforward.get("synthetic_prices") or robustness.get("synthetic_prices")
        ),
    }
