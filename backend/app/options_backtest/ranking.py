from __future__ import annotations

from typing import Any, Iterable


DEFAULT_MIN_SCORE = 50.0
DEFAULT_TOP_N = 5


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _strategy_name(item: dict[str, Any]) -> str:
    return str(item.get("strategy") or item.get("name") or "UNKNOWN")


def _rank_key(item: dict[str, Any]) -> tuple:
    # Deterministic tie-break order: quality score, OOS PF, OOS P&L,
    # lower drawdown, then higher trade count, then strategy name.
    return (
        -_num(item.get("quality_score")),
        -_num(item.get("oos_profit_factor")),
        -_num(item.get("oos_net_profit")),
        _num(item.get("max_drawdown_pct"), 999999.0),
        -_num(item.get("oos_trades")),
        _strategy_name(item).upper(),
    )


def rank_optionvault_strategies(
    strategies: Iterable[dict[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
    min_score: float = DEFAULT_MIN_SCORE,
    require_active: bool = True,
) -> dict[str, Any]:
    """Rank Phase 15 quality outputs; does not create new evidence or trades."""
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if not 0 <= min_score <= 100:
        raise ValueError("min_score must be between 0 and 100")

    normalized: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for raw in strategies:
        item = dict(raw)
        score = _num(item.get("quality_score"))
        active = bool(item.get("active", False))
        classification = str(item.get("classification") or "DISABLED").upper()

        if require_active and not active:
            excluded.append({"strategy": _strategy_name(item), "reason": "INACTIVE"})
            continue
        if classification == "DISABLED":
            excluded.append({"strategy": _strategy_name(item), "reason": "DISABLED"})
            continue
        if score < min_score:
            excluded.append({"strategy": _strategy_name(item), "reason": "BELOW_MIN_SCORE"})
            continue

        # Accept direct Phase 15 fields, with optional nested evidence fallbacks.
        wf = item.get("walkforward") or {}
        oos = (wf.get("oos_summary") or {}) if isinstance(wf, dict) else {}
        normalized.append({
            **item,
            "strategy": _strategy_name(item),
            "quality_score": score,
            "oos_profit_factor": _num(item.get("oos_profit_factor", oos.get("profit_factor"))),
            "oos_net_profit": _num(item.get("oos_net_profit", oos.get("aggregate_oos_net_profit"))),
            "oos_trades": int(_num(item.get("oos_trades", oos.get("aggregate_oos_trades")))),
            "max_drawdown_pct": _num(item.get("max_drawdown_pct"), 0.0),
        })

    normalized.sort(key=_rank_key)
    ranked = []
    for idx, item in enumerate(normalized[:top_n], start=1):
        ranked.append({**item, "rank": idx})

    return {
        "status": "OK",
        "top_n": top_n,
        "min_score": min_score,
        "total_candidates": len(normalized) + len(excluded),
        "eligible_count": len(normalized),
        "ranked": ranked,
        "excluded": excluded,
    }
