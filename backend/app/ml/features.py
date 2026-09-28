from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DEFAULT_FEATURES = (
    "ema_9",
    "ema_20",
    "ema_50",
    "rsi_14",
    "atr_14",
    "vwap_distance_pct",
    "relative_volume_20",
    "return_1",
    "return_5",
    "return_15",
    "momentum_10",
    "volatility_20",
    "distance_pdh",
    "distance_pdl",
    "distance_pdc",
)


@dataclass(frozen=True)
class FeatureMatrix:
    names: tuple[str, ...]
    rows: list[list[float]]
    timestamps: list[object]


def build_feature_matrix(
    feature_rows: Iterable[dict],
    *,
    feature_names: tuple[str, ...] = DEFAULT_FEATURES,
) -> FeatureMatrix:
    names = tuple(feature_names)
    matrix = []
    timestamps = []

    for row in feature_rows:
        values = []
        valid = True

        for name in names:
            value = row.get(name)
            if value is None:
                valid = False
                break
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                valid = False
                break

        if valid:
            matrix.append(values)
            timestamps.append(row.get("timestamp"))

    if not matrix:
        raise ValueError("No complete ML feature rows available")

    return FeatureMatrix(
        names=names,
        rows=matrix,
        timestamps=timestamps,
    )


def build_binary_target(
    closes: list[float],
    *,
    horizon: int,
    threshold: float = 0.0,
) -> list[int | None]:
    """
    Target is based on the future close relative to current close.

    y_t = 1 if (close[t+h]/close[t] - 1) > threshold else 0.

    The final horizon observations are None because the future outcome is not
    known yet. They must never enter a training set.
    """
    if horizon <= 0:
        raise ValueError("horizon must be > 0")

    target = [None] * len(closes)
    for i in range(len(closes) - horizon):
        future_return = closes[i + horizon] / closes[i] - 1.0
        target[i] = 1 if future_return > threshold else 0
    return target
