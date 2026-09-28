from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..structure.service import StructureService

router = APIRouter(prefix="/phase7", tags=["phase7"])
service = StructureService()

class CandleInput(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0

class StructureRequest(BaseModel):
    candles: list[CandleInput]

@router.post("/structure")
def analyze_structure(request: StructureRequest):
    if len(request.candles) < 7:
        raise HTTPException(400, "At least 7 candles are required")
    return service.analyze([c.model_dump() for c in request.candles])
