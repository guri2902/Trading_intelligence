
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence
import math


@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass
class OOSWindowResult:
    window_id: int
    train_metrics: Dict[str, float]
    test_metrics: Dict[str, float]
    selected_params: Dict[str, Any]
    eligible: bool
    reason: str = ""


@dataclass
class WalkForwardReport:
    windows: List[OOSWindowResult] = field(default_factory=list)
    aggregate_oos: Dict[str, float] = field(default_factory=dict)
    promoted: bool = False
    promotion_reason: str = ""


class WalkForwardValidator:
    """
    Chronological walk-forward validator.

    `optimizer` receives only the training slice and returns selected parameters.
    `tester` receives only the unseen test slice and those parameters.
    No function receives future rows from outside its assigned window.
    """

    def __init__(
        self,
        optimizer: Callable[[Sequence[Any]], tuple[Mapping[str, Any], Mapping[str, Any]]],
        tester: Callable[[Sequence[Any], Mapping[str, Any]], Mapping[str, Any]],
        *,
        train_size: int,
        test_size: int,
        step_size: Optional[int] = None,
        min_windows: int = 3,
        min_oos_trades: int = 5,
        min_oos_win_rate: Optional[float] = None,
        max_oos_drawdown_pct: Optional[float] = None,
        min_positive_windows_pct: float = 0.60,
    ):
        if train_size < 1 or test_size < 1:
            raise ValueError("train_size and test_size must be >= 1")
        self.optimizer = optimizer
        self.tester = tester
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size or test_size
        if self.step_size < 1:
            raise ValueError("step_size must be >= 1")
        self.min_windows = min_windows
        self.min_oos_trades = min_oos_trades
        self.min_oos_win_rate = min_oos_win_rate
        self.max_oos_drawdown_pct = max_oos_drawdown_pct
        self.min_positive_windows_pct = min_positive_windows_pct

    def windows(self, n: int) -> List[WalkForwardWindow]:
        result = []
        start = 0
        wid = 0
        while start + self.train_size + self.test_size <= n:
            train_start = start
            train_end = start + self.train_size
            test_start = train_end
            test_end = test_start + self.test_size
            result.append(
                WalkForwardWindow(
                    wid, train_start, train_end, test_start, test_end
                )
            )
            wid += 1
            start += self.step_size
        return result

    @staticmethod
    def _num(metrics: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
        for key in keys:
            value = metrics.get(key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                return float(value)
        return default

    def validate(self, data: Sequence[Any]) -> WalkForwardReport:
        if len(data) < self.train_size + self.test_size:
            raise ValueError("insufficient data for one train/test window")

        windows = self.windows(len(data))
        if len(windows) < self.min_windows:
            raise ValueError(f"insufficient walk-forward windows: {len(windows)}<{self.min_windows}")

        results: List[OOSWindowResult] = []
        for w in windows:
            train = list(data[w.train_start:w.train_end])
            test = list(data[w.test_start:w.test_end])

            try:
                selected_params, train_metrics = self.optimizer(train)
                if not isinstance(selected_params, Mapping):
                    raise ValueError("optimizer must return parameter mapping")
                if not isinstance(train_metrics, Mapping):
                    raise ValueError("optimizer must return training metrics mapping")

                test_metrics = dict(self.tester(test, selected_params))
                trades = int(self._num(test_metrics, "trades", "trade_count"))
                pnl = self._num(test_metrics, "net_pnl", "pnl")
                dd = abs(self._num(test_metrics, "max_drawdown_pct", "drawdown_pct"))
                win_rate = self._num(test_metrics, "win_rate")

                eligible = True
                reason_parts = []
                if trades < self.min_oos_trades:
                    eligible = False
                    reason_parts.append(f"min_oos_trades:{trades}<{self.min_oos_trades}")
                if self.min_oos_win_rate is not None and win_rate < self.min_oos_win_rate:
                    eligible = False
                    reason_parts.append(
                        f"min_oos_win_rate:{win_rate}<{self.min_oos_win_rate}"
                    )
                if self.max_oos_drawdown_pct is not None and dd > self.max_oos_drawdown_pct:
                    eligible = False
                    reason_parts.append(
                        f"max_oos_drawdown:{dd}>{self.max_oos_drawdown_pct}"
                    )
                if not math.isfinite(pnl):
                    eligible = False
                    reason_parts.append("non_finite_pnl")

                results.append(
                    OOSWindowResult(
                        w.window_id,
                        {k: float(v) for k, v in train_metrics.items()
                         if isinstance(v, (int, float)) and math.isfinite(float(v))},
                        {k: float(v) for k, v in test_metrics.items()
                         if isinstance(v, (int, float)) and math.isfinite(float(v))},
                        dict(selected_params),
                        eligible,
                        ";".join(reason_parts),
                    )
                )
            except Exception as exc:
                results.append(
                    OOSWindowResult(
                        w.window_id, {}, {}, {}, False,
                        f"window_error:{type(exc).__name__}",
                    )
                )

        oos = [r for r in results if r.eligible]
        all_test = [r for r in results if r.test_metrics]
        if not all_test:
            return WalkForwardReport(
                windows=results,
                aggregate_oos={},
                promoted=False,
                promotion_reason="no_valid_oos_results",
            )

        pnls = [self._num(r.test_metrics, "net_pnl", "pnl") for r in all_test]
        trade_counts = [self._num(r.test_metrics, "trades", "trade_count") for r in all_test]
        positive = sum(1 for x in pnls if x > 0)

        aggregate = {
            "windows": float(len(all_test)),
            "eligible_windows": float(len(oos)),
            "total_oos_pnl": float(sum(pnls)),
            "avg_oos_pnl": float(sum(pnls) / len(pnls)),
            "positive_window_pct": float(positive / len(pnls)),
            "oos_trades": float(sum(trade_counts)),
        }

        reasons = []
        promoted = True
        if len(oos) < self.min_windows:
            promoted = False
            reasons.append(f"eligible_windows:{len(oos)}<{self.min_windows}")
        if aggregate["positive_window_pct"] < self.min_positive_windows_pct:
            promoted = False
            reasons.append(
                f"positive_window_pct:{aggregate['positive_window_pct']}"
                f"<{self.min_positive_windows_pct}"
            )

        if promoted:
            promotion_reason = "passed_oos_stability_gate"
        else:
            promotion_reason = ";".join(reasons) or "failed_oos_gate"

        return WalkForwardReport(
            windows=results,
            aggregate_oos=aggregate,
            promoted=promoted,
            promotion_reason=promotion_reason,
        )
