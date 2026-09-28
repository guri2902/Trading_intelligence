
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml.ensemble import EnsembleEngine, ProbabilityCalibrator

router = APIRouter(prefix="/phase25", tags=["phase25"])


class CalibrationRequest(BaseModel):
    probabilities: List[float]
    labels: List[int]
    n_bins: int = Field(default=10, ge=2, le=50)


class EnsembleRequest(BaseModel):
    model_probabilities: Dict[str, float]
    validation_labels: List[int]
    historical_model_probabilities: Dict[str, List[float]]
    min_models: int = Field(default=2, ge=1)
    min_agreement: float = Field(default=0.50, ge=0, le=1)


@router.get("/health")
def health() -> Dict[str, str]:
    return {"phase": "25", "status": "ok"}


@router.post("/calibrate")
def calibrate(req: CalibrationRequest) -> Dict[str, Any]:
    try:
        c = ProbabilityCalibrator(req.n_bins)
        report = c.fit(req.probabilities, req.labels)
        return report.__dict__
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/ensemble")
def ensemble(req: EnsembleRequest) -> Dict[str, Any]:
    try:
        engine = EnsembleEngine(req.min_models, req.min_agreement)
        report = engine.evaluate(
            req.model_probabilities,
            req.validation_labels,
            req.historical_model_probabilities,
        )
        pred = engine.predict(req.model_probabilities, report.weights)
        return {
            "prediction": pred.__dict__,
            "evaluations": [e.__dict__ for e in report.evaluations],
            "weights": report.weights,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
