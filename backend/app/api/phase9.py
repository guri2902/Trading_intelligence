from fastapi import APIRouter, HTTPException
from ..strategies.models import StrategyContext
from ..strategies.service import StrategyService

router = APIRouter(prefix="/phase9", tags=["phase9"])
service = StrategyService()

@router.post("/strategies/evaluate")
def evaluate_strategies(context: StrategyContext):
    if len(context.candles) < 5:
        raise HTTPException(400, "At least 5 candles are required")
    return service.evaluate(context).model_dump(mode="json")
