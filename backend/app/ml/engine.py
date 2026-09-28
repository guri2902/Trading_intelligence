from __future__ import annotations

from .features import DEFAULT_FEATURES, build_binary_target, build_feature_matrix
from .models import MLConfig, MLTrainingResult, ModelMetrics, Prediction
from .models_impl import build_models, fit_model, get_feature_importance
from .evaluator import evaluate_model


class MLEngine:
    """
    Chronological ML engine.

    Important:
    - Feature rows must be sorted chronologically.
    - Targets use future prices and therefore the final horizon rows are
      discarded from training.
    - The split is chronological; no shuffle.
    """

    feature_version = "phase12-v1"

    def __init__(self, config: MLConfig | None = None):
        self.config = config or MLConfig()

    def train(
        self,
        feature_rows: list[dict],
        closes: list[float],
    ) -> tuple[MLTrainingResult, dict[str, object]]:
        if len(feature_rows) != len(closes):
            raise ValueError("feature_rows and closes must have equal length")

        matrix = build_feature_matrix(
            feature_rows,
            feature_names=DEFAULT_FEATURES,
        )
        targets = build_binary_target(
            closes,
            horizon=self.config.target_horizon,
            threshold=self.config.target_threshold,
        )

        filtered_x = []
        filtered_y = []
        filtered_ts = []

        # matrix.rows already excludes incomplete features, but its timestamps
        # may not correspond one-to-one with raw closes. Build targets by
        # matching timestamp to source row index.
        feature_by_ts = {
            row.get("timestamp"): row
            for row in feature_rows
        }

        for x, ts in zip(matrix.rows, matrix.timestamps):
            try:
                source_index = next(
                    i for i, row in enumerate(feature_rows)
                    if row.get("timestamp") == ts
                )
            except StopIteration:
                continue

            y = targets[source_index]
            if y is None:
                continue

            filtered_x.append(x)
            filtered_y.append(y)
            filtered_ts.append(ts)

        if len(filtered_x) < self.config.min_samples:
            raise ValueError(
                f"Insufficient ML samples: {len(filtered_x)} < {self.config.min_samples}"
            )

        split = int(len(filtered_x) * (1.0 - self.config.test_size))
        if split <= 0 or split >= len(filtered_x):
            raise ValueError("Invalid chronological test split")

        x_train = filtered_x[:split]
        y_train = filtered_y[:split]
        x_test = filtered_x[split:]
        y_test = filtered_y[split:]

        # Fail closed when training or test set has only one class.
        if len(set(y_train)) < 2:
            raise ValueError("Training set contains only one target class")
        if len(set(y_test)) < 2:
            raise ValueError("Test set contains only one target class")

        models = build_models(self.config.random_state)

        metrics: list[ModelMetrics] = []
        importance: dict[str, dict[str, float]] = {}
        fitted: dict[str, object] = {}

        for name, estimator in models.items():
            model = fit_model(name, estimator, x_train, y_train)
            fitted[name] = model

            metric = evaluate_model(
                name,
                model,
                x_test,
                y_test,
            )
            metrics.append(metric)

            importance[name] = get_feature_importance(
                name,
                model,
                matrix.names,
            )

        # Primary ranking: balanced accuracy + ROC AUC + Brier (lower is better)
        def rank_key(metric: ModelMetrics):
            auc = metric.roc_auc or 0.0
            brier = metric.brier_score if metric.brier_score is not None else 1.0
            return (
                metric.balanced_accuracy or 0.0,
                auc,
                -brier,
                metric.f1 or 0.0,
            )

        best = max(metrics, key=rank_key)

        train_result = MLTrainingResult(
            feature_version=self.feature_version,
            target_definition=(
                f"future_return_{self.config.target_horizon}bars"
                f"_greater_than_{self.config.target_threshold}"
            ),
            train_samples=len(x_train),
            test_samples=len(x_test),
            class_balance={
                "0": int(sum(1 for y in filtered_y if y == 0)),
                "1": int(sum(1 for y in filtered_y if y == 1)),
            },
            metrics=metrics,
            best_model=best.model,
            feature_importance=importance,
            warnings=[],
        )

        state = {
            "models": fitted,
            "feature_names": matrix.names,
            "training_end_timestamp": filtered_ts[split - 1],
            "test_timestamps": filtered_ts[split:],
        }

        return train_result, state

    def predict(
        self,
        state: dict[str, object],
        feature_row: dict,
        *,
        timestamp,
    ) -> list[Prediction]:
        names = state["feature_names"]
        values = []
        for name in names:
            value = feature_row.get(name)
            if value is None:
                raise ValueError(f"Missing ML feature: {name}")
            values.append(float(value))

        predictions = []

        for name, model in state["models"].items():
            prediction = model.predict([values])[0]

            if hasattr(model, "predict_proba"):
                probs = model.predict_proba([values])[0]
                probability_down = float(probs[0])
                probability_up = float(probs[1])
                confidence = max(probability_up, probability_down)
            else:
                probability_down = None
                probability_up = None
                confidence = 0.5

            predictions.append(
                Prediction(
                    timestamp=timestamp,
                    model=name,
                    probability_up=probability_up,
                    probability_down=probability_down,
                    predicted_class=int(prediction),
                    confidence=confidence,
                    feature_version=self.feature_version,
                    training_end_timestamp=state["training_end_timestamp"],
                )
            )

        return predictions
