from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class ModelBundle:
    name: str
    pipeline: Any
    feature_names: tuple[str, ...]
    training_end_timestamp: object | None = None


def build_models(random_state: int = 42) -> dict[str, Any]:
    try:
        from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for the Phase 12 ML engine."
        ) from exc

    models = {
        "LOGISTIC_REGRESSION": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2000,
                        random_state=random_state,
                    ),
                ),
            ]
        ),
        "RANDOM_FOREST": RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=5,
            random_state=random_state,
            n_jobs=-1,
            class_weight="balanced",
        ),
        "HIST_GRADIENT_BOOSTING": HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=250,
            max_leaf_nodes=15,
            min_samples_leaf=10,
            random_state=random_state,
        ),
    }

    return models


def fit_model(
    name: str,
    estimator: Any,
    x_train,
    y_train,
) -> Any:
    estimator.fit(x_train, y_train)
    return estimator


def get_feature_importance(
    model_name: str,
    estimator: Any,
    feature_names: tuple[str, ...],
) -> dict[str, float]:
    """
    Normalizes model-specific importance into a comparable mapping.

    Logistic regression uses absolute coefficients.
    Tree ensembles use feature_importances_.
    """
    model = estimator

    if hasattr(model, "named_steps") and "model" in model.named_steps:
        model = model.named_steps["model"]

    if hasattr(model, "coef_"):
        values = np.abs(model.coef_[0])
    elif hasattr(model, "feature_importances_"):
        values = np.asarray(model.feature_importances_)
    else:
        return {}

    values = values.astype(float)
    total = float(values.sum())

    if total > 0:
        values = values / total

    return {
        name: float(value)
        for name, value in zip(feature_names, values)
    }


def predict_probabilities(estimator: Any, x):
    if hasattr(estimator, "predict_proba"):
        probs = estimator.predict_proba(x)
        if probs.shape[1] == 2:
            return probs[:, 0], probs[:, 1]
    predictions = estimator.predict(x)
    return 1.0 - predictions, predictions
