from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class MLConfig(BaseModel):
    target_horizon: int = Field(default=5, ge=1)
    target_threshold: float = Field(default=0.0)
    min_samples: int = Field(default=100, ge=20)
    test_size: float = Field(default=0.2, gt=0, lt=0.9)
    random_state: int = 42


class Prediction(BaseModel):
    timestamp: datetime | str
    model: str
    probability_up: float | None = Field(default=None, ge=0, le=1)
    probability_down: float | None = Field(default=None, ge=0, le=1)
    predicted_class: int | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    feature_version: str = "phase12-v1"
    training_end_timestamp: datetime | str | None = None


class ModelMetrics(BaseModel):
    model: str
    samples: int
    accuracy: float | None = None
    balanced_accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    roc_auc: float | None = None
    brier_score: float | None = None
    log_loss: float | None = None


class MLTrainingResult(BaseModel):
    feature_version: str
    target_definition: str
    train_samples: int
    test_samples: int
    class_balance: dict[str, int]
    metrics: list[ModelMetrics]
    best_model: str | None = None
    feature_importance: dict[str, dict[str, float]] = {}
    warnings: list[str] = []
