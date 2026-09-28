from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db.models import Candle, Instrument, MarketSnapshot


def latest_candles(
    db: Session,
    *,
    instrument_key: str,
    timeframe: str,
    limit: int = 200,
) -> list[Candle]:
    instrument = db.scalar(
        select(Instrument).where(
            Instrument.instrument_key == instrument_key
        )
    )
    if instrument is None:
        return []

    stmt = (
        select(Candle)
        .where(
            Candle.instrument_id == instrument.id,
            Candle.timeframe == timeframe,
        )
        .order_by(desc(Candle.timestamp))
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    return list(reversed(rows))


def latest_option_snapshot(
    db: Session,
    *,
    instrument_ids: list[int],
    source: str,
) -> list[MarketSnapshot]:
    if not instrument_ids:
        return []

    max_ts_stmt = select(
        MarketSnapshot.timestamp
    ).where(
        MarketSnapshot.instrument_id.in_(instrument_ids),
        MarketSnapshot.source == source,
    ).order_by(desc(MarketSnapshot.timestamp)).limit(1)

    latest = db.scalar(max_ts_stmt)
    if latest is None:
        return []

    stmt = select(MarketSnapshot).where(
        MarketSnapshot.instrument_id.in_(instrument_ids),
        MarketSnapshot.source == source,
        MarketSnapshot.timestamp == latest,
    )
    return list(db.scalars(stmt).all())
