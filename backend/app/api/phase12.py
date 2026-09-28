from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ml.engine import MLEngine
from ..ml.models import MLConfig

router = APIRouter(prefix="/phase12", tags=["phase12"])


class MLTrainingRequest(BaseModel):
    feature_rows: list[dict]
    closes: list[float]
    config: MLConfig = Field(default_factory=MLConfig)


@router.post("/train")
def train(request: MLTrainingRequest):
    try:
        engine = MLEngine(request.config)
        result, _ = engine.train(
            request.feature_rows,
            request.closes,
        )
        return result.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
