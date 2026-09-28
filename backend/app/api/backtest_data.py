from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Instrument
from ..db.session import get_db
from ..storage.query import latest_candles

router = APIRouter(prefix="/backtest-data", tags=["backtest-data"])


@router.get("/candles")
def get_backtest_candles(
    canonical_key: str = Query("NSE_INDEX|Nifty 50"),
    timeframe: str = Query("minutes:5"),
    limit: int = Query(500, ge=15, le=5000),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    source: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    instrument = db.scalar(
        select(Instrument).where(Instrument.instrument_key == canonical_key)
    )
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    rows = latest_candles(
        db,
        instrument_key=canonical_key,
        timeframe=timeframe,
        limit=limit,
    )

    filtered = []
    for row in rows:
        ts = row.timestamp.date()
        if from_date and ts < from_date:
            continue
        if to_date and ts > to_date:
            continue
        if source and row.source != source:
            continue
        if row.quality_status and row.quality_status.upper() != "PASS":
            continue
        filtered.append(row)

    if not filtered:
        return {
            "instrument_key": canonical_key,
            "timeframe": timeframe,
            "count": 0,
            "source": source,
            "rows": [],
        }

    return {
        "instrument_key": canonical_key,
        "timeframe": timeframe,
        "count": len(filtered),
        "source": source or filtered[-1].source,
        "from": filtered[0].timestamp.isoformat(),
        "to": filtered[-1].timestamp.isoformat(),
        "rows": [
            {
                "timestamp": row.timestamp.isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": row.volume,
                "open_interest": row.open_interest,
            }
            for row in filtered
        ],
    }
