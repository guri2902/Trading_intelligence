from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..features.service import FeatureService

router=APIRouter(prefix="/phase6",tags=["phase6"])
service=FeatureService()

class CandleInput(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

class FeatureRequest(BaseModel):
    candles:list[CandleInput]
    session_ids:list[str]|None=None

class MultiTimeframeRequest(BaseModel):
    candles:dict[str,list[CandleInput]]
    session_ids:dict[str,list[str]]|None=None

@router.post("/features")
def calculate_features(request:FeatureRequest):
    if request.session_ids and len(request.session_ids)!=len(request.candles):
        raise HTTPException(400,"session_ids length must equal candle length")
    return service.calculate([c.model_dump() for c in request.candles], request.session_ids)

@router.post("/features/multi-timeframe")
def calculate_multi(request:MultiTimeframeRequest):
    rows={tf:[c.model_dump() for c in cs] for tf,cs in request.candles.items()}
    if request.session_ids:
        for tf,s in request.session_ids.items():
            if tf in rows and len(s)!=len(rows[tf]):
                raise HTTPException(400,f"session_ids length mismatch for {tf}")
    return service.calculate_multi_timeframe(rows, request.session_ids)
