
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..backtest.models import BacktestResult
from ..strategy_studio.executor import backtest_saved_strategy
from ..strategy_studio.models import (
    BUILT_IN_STRATEGIES,
    StrategyBacktestRequest,
    StrategyCreateRequest,
    StrategyUpdateRequest,
)
from ..strategy_studio.store import StrategyStore

router = APIRouter(prefix="/strategy-studio", tags=["strategy-studio"])
store = StrategyStore()


@router.get("/engine-strategies")
def engine_strategies():
    return {"strategies": BUILT_IN_STRATEGIES}


@router.get("/strategies")
def list_strategies():
    return {"strategies": [x.model_dump(mode="json") for x in store.list()]}


@router.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str):
    try:
        return store.get(strategy_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND") from exc


@router.post("/strategies")
def create_strategy(req: StrategyCreateRequest):
    return store.create(req).model_dump(mode="json")


@router.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: str, req: StrategyUpdateRequest):
    try:
        return store.update(strategy_id, req).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND") from exc


@router.post("/strategies/{strategy_id}/enable")
def enable_strategy(strategy_id: str):
    try:
        return store.set_status(strategy_id, "ACTIVE").model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND") from exc


@router.post("/strategies/{strategy_id}/disable")
def disable_strategy(strategy_id: str):
    try:
        return store.set_status(strategy_id, "DISABLED").model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND") from exc


@router.post("/strategies/{strategy_id}/duplicate")
def duplicate_strategy(strategy_id: str):
    try:
        return store.duplicate(strategy_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND") from exc


@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: str):
    try:
        store.delete(strategy_id)
        return {"status": "DELETED", "strategy_id": strategy_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND") from exc


@router.get("/strategies/{strategy_id}/versions")
def list_versions(strategy_id: str):
    try:
        item = store.get(strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND") from exc
    return {
        "strategy_id": strategy_id,
        "current_version": item.version,
        "versions": [x.model_dump(mode="json") for x in item.versions],
    }


@router.post("/strategies/{strategy_id}/backtest")
def backtest_strategy(strategy_id: str, req: StrategyBacktestRequest):
    try:
        strategy = store.get(strategy_id)
        result = backtest_saved_strategy(strategy, req)
        return result.model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
