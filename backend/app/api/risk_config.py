from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..risk_config.models import RiskCalculationRequest, RiskConfig
from ..risk_config.service import LotRiskCalculator, RiskConfigService

router = APIRouter(prefix="/risk-config", tags=["risk-config"])

service = RiskConfigService()
calculator = LotRiskCalculator(service)


@router.get("")
def get_risk_config():
    return service.get().model_dump(mode="json")


@router.put("")
def save_risk_config(config: RiskConfig):
    return service.save(config).model_dump(mode="json")


@router.post("/calculate")
def calculate_risk(req: RiskCalculationRequest):
    try:
        return calculator.calculate(req).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
