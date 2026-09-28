from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Instrument, InstrumentAlias
from .identity import canonical_identity
from .models import InstrumentRecord


def upsert_instrument(db: Session, record: InstrumentRecord) -> Instrument:
    now = datetime.now(timezone.utc)

    existing = db.scalar(
        select(Instrument).where(
            Instrument.instrument_key == record.instrument_key
        )
    )

    if existing is None:
        existing = Instrument(
            instrument_key=record.instrument_key,
            created_at=now,
        )
        db.add(existing)

    identity = canonical_identity(
        exchange=record.exchange,
        segment=record.segment,
        trading_symbol=record.trading_symbol,
        instrument_type=record.instrument_type,
        expiry_date=record.expiry_date,
        strike=record.strike,
        option_type=record.option_type,
    )

    existing.instrument_key = identity
    existing.exchange = record.exchange.upper()
    existing.segment = record.segment.upper()
    existing.instrument_type = record.instrument_type.upper()
    existing.trading_symbol = record.trading_symbol.upper()
    existing.underlying_key = record.underlying_key
    existing.underlying_symbol = (
        record.underlying_symbol.upper()
        if record.underlying_symbol
        else None
    )
    existing.expiry_date = record.expiry_date
    existing.strike = record.strike
    existing.option_type = record.option_type
    existing.lot_size = record.lot_size
    existing.tick_size = record.tick_size
    existing.is_active = record.is_active
    existing.source = record.source
    existing.source_updated_at = record.source_updated_at
    existing.updated_at = now

    db.flush()

    return existing


def upsert_alias(
    db: Session,
    instrument: Instrument,
    *,
    source: str,
    source_key: str,
    source_symbol: str | None = None,
) -> InstrumentAlias:
    alias = db.scalar(
        select(InstrumentAlias).where(
            InstrumentAlias.source == source,
            InstrumentAlias.source_key == source_key,
        )
    )
    if alias is None:
        alias = InstrumentAlias(
            instrument_id=instrument.id,
            source=source,
            source_key=source_key,
            source_symbol=source_symbol,
            created_at=datetime.now(timezone.utc),
        )
        db.add(alias)
    else:
        alias.instrument_id = instrument.id
        alias.source_symbol = source_symbol

    return alias


def find_by_alias(
    db: Session,
    source: str,
    source_key: str,
) -> Instrument | None:
    stmt = (
        select(Instrument)
        .join(
            InstrumentAlias,
            InstrumentAlias.instrument_id == Instrument.id,
        )
        .where(
            InstrumentAlias.source == source,
            InstrumentAlias.source_key == source_key,
        )
    )
    return db.scalar(stmt)


def sync_records(
    db: Session,
    records: Iterable[InstrumentRecord],
) -> int:
    count = 0
    for record in records:
        instrument = upsert_instrument(db, record)
        upsert_alias(
            db,
            instrument,
            source=record.source,
            source_key=record.instrument_key,
            source_symbol=record.trading_symbol,
        )
        count += 1

    db.commit()
    return count
