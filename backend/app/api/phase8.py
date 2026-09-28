from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..options.engine import OptionsEngine
from ..options.models import OptionQuoteState

router = APIRouter(prefix="/phase8", tags=["phase8"])
engine = OptionsEngine()


class OptionsRequest(BaseModel):
    quotes: list[OptionQuoteState]
    preferred_expiry: date | None = None
    now: datetime | None = None
    atm_distance: float = Field(default=100000.0, gt=0)


@router.post("/options/analyze")
def analyze_options(request: OptionsRequest):
    if not request.quotes:
        raise HTTPException(400, "Option chain is empty")
    return engine.analyze(
        request.quotes,
        preferred_expiry=request.preferred_expiry,
        now=request.now,
        atm_distance=request.atm_distance,
    )
