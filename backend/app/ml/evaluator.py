from __future__ import annotations

from typing import Any

import numpy as np

from .models import ModelMetrics
from .models_impl import predict_probabilities


def evaluate_model(
    model_name: str,
    estimator: Any,
    x_test,
    y_test,
) -> ModelMetrics:
    try:
        from sklearn.metrics import (
            accuracy_score,
            balanced_accuracy_score,
            brier_score_loss,
            f1_score,
            log_loss,
            precision_score,
            recall_score,
            roc_auc_score,
        )
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for ML evaluation."
        ) from exc

    y_pred = estimator.predict(x_test)
    p_down, p_up = predict_probabilities(estimator, x_test)

    accuracy = accuracy_score(y_test, y_pred)
    balanced = balanced_accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    try:
        auc = roc_auc_score(y_test, p_up)
    except ValueError:
        auc = None

    try:
        brier = brier_score_loss(y_test, p_up)
    except ValueError:
        brier = None

    try:
        ll = log_loss(y_test, np.column_stack([p_down, p_up]), labels=[0, 1])
    except ValueError:
        ll = None

    return ModelMetrics(
        model=model_name,
        samples=len(y_test),
        accuracy=float(accuracy),
        balanced_accuracy=float(balanced),
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        roc_auc=float(auc) if auc is not None else None,
        brier_score=float(brier) if brier is not None else None,
        log_loss=float(ll) if ll is not None else None,
    )
