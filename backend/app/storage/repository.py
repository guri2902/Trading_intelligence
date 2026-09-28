from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Candle, DataQualityEvent, Instrument, MarketSnapshot
from .quality import QualityResult


def find_instrument(
    db: Session,
    canonical_key: str,
) -> Instrument | None:
    return db.scalar(
        select(Instrument).where(
            Instrument.instrument_key == canonical_key
        )
    )


def persist_candles(
    db: Session,
    *,
    instrument: Instrument,
    timeframe: str,
    rows: Iterable[dict],
    source: str,
    quality_status: str,
) -> int:
    inserted = 0

    for row in rows:
        timestamp = row["timestamp"]
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        existing = db.scalar(
            select(Candle).where(
                Candle.instrument_id == instrument.id,
                Candle.timeframe == timeframe,
                Candle.timestamp == timestamp,
                Candle.source == source,
            )
        )

        if existing:
            existing.open = Decimal(str(row["open"]))
            existing.high = Decimal(str(row["high"]))
            existing.low = Decimal(str(row["low"]))
            existing.close = Decimal(str(row["close"]))
            existing.volume = (
                int(row["volume"]) if row.get("volume") is not None else None
            )
            existing.open_interest = (
                int(row["open_interest"])
                if row.get("open_interest") is not None
                else None
            )
            existing.quality_status = quality_status
            continue

        db.add(
            Candle(
                instrument_id=instrument.id,
                timeframe=timeframe,
                timestamp=timestamp,
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=int(row["volume"]) if row.get("volume") is not None else None,
                open_interest=(
                    int(row["open_interest"])
                    if row.get("open_interest") is not None
                    else None
                ),
                source=source,
                quality_status=quality_status,
            )
        )
        inserted += 1

    db.commit()
    return inserted


def persist_option_snapshot(
    db: Session,
    *,
    instrument_rows: Iterable[tuple[Instrument, dict]],
    timestamp: datetime,
    source: str,
    quality_status: str,
) -> int:
    inserted = 0

    for instrument, row in instrument_rows:
        existing = db.scalar(
            select(MarketSnapshot).where(
                MarketSnapshot.instrument_id == instrument.id,
                MarketSnapshot.timestamp == timestamp,
                MarketSnapshot.source == source,
            )
        )

        values = dict(
            underlying_ltp=_decimal(row.get("underlying_ltp")),
            ltp=_decimal(row.get("ltp")),
            bid=_decimal(row.get("bid")),
            ask=_decimal(row.get("ask")),
            bid_qty=_int(row.get("bid_qty")),
            ask_qty=_int(row.get("ask_qty")),
            volume=_int(row.get("volume")),
            open_interest=_int(row.get("open_interest")),
            change_in_oi=_int(row.get("change_in_oi")),
            iv=_decimal(row.get("iv")),
            delta=_decimal(row.get("delta")),
            gamma=_decimal(row.get("gamma")),
            theta=_decimal(row.get("theta")),
            vega=_decimal(row.get("vega")),
            rho=_decimal(row.get("rho")),
            quality_status=quality_status,
        )

        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            continue

        db.add(
            MarketSnapshot(
                instrument_id=instrument.id,
                timestamp=timestamp,
                source=source,
                **values,
            )
        )
        inserted += 1

    db.commit()
    return inserted


def record_quality_event(
    db: Session,
    *,
    source: str,
    instrument_key: str | None,
    event_type: str,
    severity: str,
    details: str,
    event_time: datetime | None = None,
) -> int:
    event_time = event_time or datetime.now(timezone.utc)

    event = DataQualityEvent(
        source=source,
        instrument_key=instrument_key,
        event_type=event_type,
        severity=severity,
        event_time=event_time,
        details=details,
        resolved=False,
    )
    db.add(event)
    db.commit()
    return event.id


def quality_to_payload(result: QualityResult) -> dict:
    return {
        "status": result.status,
        "signal_safe": result.signal_safe,
        "reason": result.reason,
        "stale": result.stale,
        "duplicate_count": result.duplicate_count,
        "gap_count": result.gap_count,
        "malformed_count": result.malformed_count,
    }


def _decimal(value):
    return Decimal(str(value)) if value is not None else None


def _int(value):
    return int(value) if value is not None else None
