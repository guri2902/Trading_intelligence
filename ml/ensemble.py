
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Sequence
import math


@dataclass
class CalibrationReport:
    method: str
    sample_count: int
    brier_before: float
    brier_after: float
    mean_probability: float
    observed_rate: float


@dataclass
class EnsemblePrediction:
    probability: float
    label: str
    model_probabilities: Dict[str, float]
    weights: Dict[str, float]
    agreement: float
    calibrated: bool


@dataclass
class ModelEvaluation:
    name: str
    probability: float
    brier: float
    log_loss: float
    weight: float


@dataclass
class EnsembleReport:
    evaluations: List[ModelEvaluation] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)
    calibrated: bool = False
    calibration: CalibrationReport | None = None


class ProbabilityCalibrator:
    """
    Lightweight leakage-safe calibration using chronological validation samples.

    The fitted calibrator is monotonic piecewise-linear based on probability
    bins; it never uses future labels and remains deterministic.
    """

    def __init__(self, n_bins: int = 10):
        if n_bins < 2:
            raise ValueError("n_bins must be >= 2")
        self.n_bins = n_bins
        self.bin_rates: List[float] | None = None
        self.bin_counts: List[int] | None = None

    def fit(self, probabilities: Sequence[float], labels: Sequence[int]) -> CalibrationReport:
        if len(probabilities) != len(labels) or not probabilities:
            raise ValueError("probabilities and labels must be non-empty and same length")
        clean_p, clean_y = [], []
        for p, y in zip(probabilities, labels):
            p = float(p)
            y = int(y)
            if not math.isfinite(p) or p < 0 or p > 1 or y not in (0, 1):
                raise ValueError("invalid calibration sample")
            clean_p.append(p)
            clean_y.append(y)

        rates, counts = [], []
        for b in range(self.n_bins):
            lo = b / self.n_bins
            hi = (b + 1) / self.n_bins
            idx = [i for i, p in enumerate(clean_p)
                   if (lo <= p < hi) or (b == self.n_bins - 1 and p <= hi)]
            counts.append(len(idx))
            rates.append(sum(clean_y[i] for i in idx) / len(idx) if idx else math.nan)

        # Fill empty bins by nearest non-empty bin, keeping monotonicity.
        for i in range(self.n_bins):
            if math.isnan(rates[i]):
                nearest = min(
                    (j for j in range(self.n_bins) if not math.isnan(rates[j])),
                    key=lambda j: abs(j - i),
                    default=None,
                )
                rates[i] = rates[nearest] if nearest is not None else sum(clean_y) / len(clean_y)

        # Isotonic-style monotonic pass.
        for i in range(1, self.n_bins):
            if rates[i] < rates[i - 1]:
                rates[i] = rates[i - 1]

        self.bin_rates = rates
        self.bin_counts = counts

        before = sum((p-y)**2 for p, y in zip(clean_p, clean_y)) / len(clean_y)
        after = sum((self.transform(p)-y)**2 for p, y in zip(clean_p, clean_y)) / len(clean_y)
        return CalibrationReport(
            method="chronological_binned_monotonic",
            sample_count=len(clean_y),
            brier_before=before,
            brier_after=after,
            mean_probability=sum(clean_p)/len(clean_p),
            observed_rate=sum(clean_y)/len(clean_y),
        )

    def transform(self, probability: float) -> float:
        if self.bin_rates is None:
            raise RuntimeError("calibrator is not fitted")
        p = min(max(float(probability), 0.0), 1.0)
        x = p * self.n_bins
        left = min(int(x), self.n_bins - 1)
        right = min(left + 1, self.n_bins - 1)
        frac = x - int(x)
        value = self.bin_rates[left] * (1-frac) + self.bin_rates[right] * frac
        return min(max(value, 0.0), 1.0)


class EnsembleEngine:
    def __init__(self, min_models: int = 2, min_agreement: float = 0.50):
        if min_models < 1:
            raise ValueError("min_models must be >= 1")
        if not 0 <= min_agreement <= 1:
            raise ValueError("min_agreement must be in [0,1]")
        self.min_models = min_models
        self.min_agreement = min_agreement

    @staticmethod
    def _brier(p: float, y: int) -> float:
        return (p-y)**2

    @staticmethod
    def _log_loss(p: float, y: int) -> float:
        p = min(max(p, 1e-12), 1-1e-12)
        return -(y*math.log(p) + (1-y)*math.log(1-p))

    def evaluate(
        self,
        model_probabilities: Mapping[str, float],
        validation_labels: Sequence[int],
        historical_model_probabilities: Mapping[str, Sequence[float]],
    ) -> EnsembleReport:
        if len(model_probabilities) < self.min_models:
            raise ValueError("insufficient models for ensemble")
        evaluations = []
        for name, current in model_probabilities.items():
            hist = list(historical_model_probabilities.get(name, []))
            if len(hist) != len(validation_labels) or not hist:
                raise ValueError(f"missing chronological validation samples for {name}")
            brier = sum(self._brier(float(p), int(y)) for p, y in zip(hist, validation_labels)) / len(hist)
            logloss = sum(self._log_loss(float(p), int(y)) for p, y in zip(hist, validation_labels)) / len(hist)
            weight = 1.0 / max(brier, 1e-6)
            evaluations.append(ModelEvaluation(name, float(current), brier, logloss, weight))

        total = sum(e.weight for e in evaluations)
        weights = {e.name: e.weight/total for e in evaluations}
        return EnsembleReport(evaluations=evaluations, weights=weights)

    def predict(
        self,
        model_probabilities: Mapping[str, float],
        weights: Mapping[str, float],
        calibrator: ProbabilityCalibrator | None = None,
    ) -> EnsemblePrediction:
        if len(model_probabilities) < self.min_models:
            raise ValueError("insufficient models for ensemble")
        usable = []
        for name, p in model_probabilities.items():
            p = float(p)
            if not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError(f"invalid probability for {name}")
            if name not in weights:
                raise ValueError(f"missing weight for {name}")
            usable.append((name, p))
        denom = sum(weights[n] for n, _ in usable)
        if denom <= 0:
            raise ValueError("ensemble weights must sum positive")
        raw = sum(p * weights[n] for n, p in usable) / denom
        calibrated = calibrator is not None
        probability = calibrator.transform(raw) if calibrator else raw
        directions = [1 if p >= 0.5 else 0 for _, p in usable]
        majority = sum(directions) / len(directions)
        agreement = max(majority, 1-majority)
        return EnsemblePrediction(
            probability=probability,
            label="POSITIVE" if probability >= 0.5 else "NEGATIVE",
            model_probabilities=dict(model_probabilities),
            weights={n: weights[n]/denom for n, _ in usable},
            agreement=agreement,
            calibrated=calibrated,
        )
