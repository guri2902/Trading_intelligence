from datetime import datetime, timedelta, timezone

import pytest

from backend.app.ml.features import build_binary_target
from backend.app.ml.engine import MLEngine
from backend.app.ml.models import MLConfig


def make_dataset(n=220):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    closes = []

    for i in range(n):
        # Deterministic oscillation + slow trend so both target classes exist.
        ret_signal = 0.5 if (i // 5) % 2 == 0 else -0.45
        close = 100 + i * 0.02 + ret_signal
        closes.append(close)
        rows.append({
            "timestamp": start + timedelta(minutes=i),
            "ema_9": close + 0.2,
            "ema_20": close,
            "ema_50": close - 0.2,
            "rsi_14": 55 if i % 4 < 2 else 45,
            "atr_14": 1.0,
            "vwap_distance_pct": (0.002 if i % 3 else -0.002),
            "relative_volume_20": 1.2 + (i % 5) * 0.1,
            "return_1": 0.001 if i % 2 else -0.001,
            "return_5": 0.003 if (i // 5) % 2 == 0 else -0.003,
            "return_15": 0.004 if (i // 10) % 2 == 0 else -0.004,
            "momentum_10": 0.5 if (i // 5) % 2 == 0 else -0.5,
            "volatility_20": 0.01,
            "distance_pdh": 1.0 if i % 3 else -1.0,
            "distance_pdl": 2.0,
            "distance_pdc": 0.5 if i % 2 else -0.5,
        })

    return rows, closes


def test_target_discards_future_unknown_rows():
    target = build_binary_target([100, 101, 102, 103, 104], horizon=2)
    assert target[-2:] == [None, None]
    assert target[0] in {0, 1}


@pytest.mark.skipif(
    pytest.importorskip("sklearn", reason="scikit-learn not installed") is None,
    reason="sklearn unavailable",
)
def test_ml_engine_trains_chronologically():
    rows, closes = make_dataset()

    config = MLConfig(
        target_horizon=3,
        target_threshold=0.0,
        min_samples=100,
        test_size=0.2,
        random_state=42,
    )

    result, state = MLEngine(config).train(rows, closes)

    assert result.train_samples > result.test_samples
    assert result.best_model in {
        "LOGISTIC_REGRESSION",
        "RANDOM_FOREST",
        "HIST_GRADIENT_BOOSTING",
    }
    assert len(result.metrics) == 3
    assert state["training_end_timestamp"] < state["test_timestamps"][0]


def test_ml_engine_fails_on_too_few_samples():
    rows, closes = make_dataset(40)
    with pytest.raises(ValueError):
        MLEngine(
            MLConfig(
                min_samples=100,
                target_horizon=5,
            )
        ).train(rows, closes)
