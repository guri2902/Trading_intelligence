from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..data.historical_parquet import HistoricalParquetDataService, HistoricalQuery
from ..options_backtest.engine import HistoricalOptionsBacktestEngine
from ..options_backtest.models import OptionsBacktestConfig

router = APIRouter(prefix="/phase21", tags=["phase21"])


class DriveHistoricalOptionsRequest(BaseModel):
    strategy_name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    from_date: date | None = None
    to_date: date | None = None
    expiry: date | None = None
    strike: float | None = None
    side: str | None = None
    signal: dict
    config: OptionsBacktestConfig = Field(default_factory=OptionsBacktestConfig)


@router.get("/drive-data/health")
def drive_data_health():
    return HistoricalParquetDataService().health()


@router.post("/backtest/drive")
def backtest_from_drive(req: DriveHistoricalOptionsRequest):
    service = HistoricalParquetDataService()
    bars = service.option_bars(
        HistoricalQuery(
            symbol=req.symbol,
            from_date=req.from_date,
            to_date=req.to_date,
            expiry=req.expiry,
            strike=req.strike,
            side=req.side,
        )
    )
    if not bars:
        raise HTTPException(status_code=404, detail="NO_HISTORICAL_OPTION_DATA")

    result = HistoricalOptionsBacktestEngine().run(
        bars,
        lambda _ctx: req.signal,
        strategy_name=req.strategy_name,
        config=req.config,
    )
    return result.model_dump()
