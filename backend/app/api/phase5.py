from __future__ import annotations

from datetime import date, time, timedelta, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Instrument, Candle
from ..db.session import get_db
from ..data_service import DataService
from ..instruments.universe import get_core_option_instruments
from ..storage.ingestion import ingest_option_chain as persist_option_chain, ingest_provider_candles
from ..storage.query import latest_candles, latest_option_snapshot

router = APIRouter(prefix="/phase5", tags=["phase5"])
data_service = DataService()


@router.post("/ingest/candles")
def ingest_candles(
    provider: str = Query("upstox"),
    instrument_key: str = Query(...),
    canonical_key: str = Query(...),
    unit: str = Query("minutes"),
    interval: int = Query(1, ge=1),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
):
    instrument = db.scalar(
        select(Instrument).where(
            Instrument.instrument_key == canonical_key
        )
    )
    if instrument is None:
        index_map = {
            "NSE_INDEX|Nifty 50": "NIFTY",
            "NSE_INDEX|Nifty Bank": "BANKNIFTY",
        }

        trading_symbol = index_map.get(canonical_key)

        if trading_symbol:
            instrument = db.scalar(
                select(Instrument).where(
                    Instrument.segment == "NSE_INDEX",
                    Instrument.trading_symbol == trading_symbol,
                )
            )

    if instrument is None:
        raise HTTPException(
            status_code=404,
            detail=f"Canonical instrument not found: {canonical_key}",
        )
    
    provider_obj = data_service.providers.get(provider)
    if provider_obj is None or not hasattr(provider_obj, "candles"):
        raise HTTPException(status_code=404, detail="Provider not available")

    candles = provider_obj.candles(
        instrument_key,
        unit,
        interval,
        from_date,
        to_date,
    )

    # Provider returns Candle objects, while the quality/persistence
    # pipeline expects dictionaries.
    candle_rows = [
        {
            "timestamp": candle.timestamp,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "open_interest": candle.open_interest,
        }
        for candle in candles
    ]

    return ingest_provider_candles(
        db,
        instrument=instrument,
        timeframe=f"{unit}:{interval}",
        candles=candle_rows,
        expected_interval_minutes=interval if unit == "minutes" else None,
        source=provider,
    )


@router.post("/ingest/option-chain")
def ingest_option_chain(
    provider: str = Query("upstox"),
    underlying_key: str = Query(...),
    expiry_date: date | None = Query(default=None),
    underlying_symbol: str = Query("NIFTY"),
    db: Session = Depends(get_db),
):
    provider_obj = data_service.providers.get(provider)
    if provider_obj is None or not hasattr(provider_obj, "option_chain"):
        raise HTTPException(status_code=404, detail="Provider not available")

    snapshot = provider_obj.option_chain(
        underlying_key,
        expiry_date,
    )

    instruments = get_core_option_instruments(
        db,
        underlying_symbol,
    )

    lookup = {
        (
            instrument.expiry_date,
            float(instrument.strike),
            instrument.option_type,
        ): instrument
        for instrument in instruments
        if instrument.expiry_date is not None
        and instrument.strike is not None
        and instrument.option_type is not None
    }

    return persist_option_chain(
        db,
        snapshot=snapshot,
        instrument_lookup=lookup,
        source=provider,
    )


@router.get("/candles/latest")
def get_latest_candles(
    db: Session = Depends(get_db),
    canonical_key: str = Query(...),
    timeframe: str = Query(...),
    limit: int = Query(500, ge=1, le=50000),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail="from_date cannot be after to_date",
        )

    # Resolve the API canonical key to the persisted instrument.
    instrument = (
        db.query(Instrument)
        .filter(
            Instrument.segment == "NSE_INDEX",
            Instrument.trading_symbol == "NIFTY",
        )
        .first()
    )

    if instrument is None:
        raise HTTPException(
            status_code=404,
            detail=f"Canonical NIFTY instrument not found: {canonical_key}",
        )

    query = (
        db.query(Candle)
        .filter(
            Candle.instrument_id == instrument.id,
            Candle.timeframe == timeframe,
            Candle.source == "upstox",
        )
    )

    if from_date:
        start_dt = datetime.combine(from_date, time.min)
        query = query.filter(Candle.timestamp >= start_dt)

    if to_date:
        end_dt = datetime.combine(
            to_date + timedelta(days=1),
            time.min,
        )
        query = query.filter(Candle.timestamp < end_dt)

    rows = (
        query
        .order_by(Candle.timestamp.asc())
        .limit(int(limit))
        .all()
    )

    return rows