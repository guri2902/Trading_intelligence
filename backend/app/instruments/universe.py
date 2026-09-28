from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Instrument


CORE_UNDERLYINGS = {
    "NIFTY",
    "NIFTY 50",
    "BANKNIFTY",
    "NIFTY BANK",
}


def get_core_index_instruments(db: Session) -> list[Instrument]:
    stmt = (
        select(Instrument)
        .where(
            Instrument.segment == "NSE_INDEX",
            Instrument.instrument_type == "INDEX",
        )
        .order_by(Instrument.trading_symbol)
    )
    return list(db.scalars(stmt).all())


def get_core_option_instruments(
    db: Session,
    underlying_symbol: str,
) -> list[Instrument]:
    stmt = (
        select(Instrument)
        .where(
            Instrument.segment == "NSE_FO",
            Instrument.instrument_type.in_(["CE", "PE"]),
            Instrument.underlying_symbol == underlying_symbol.upper(),
            Instrument.is_active.is_(True),
        )
        .order_by(
            Instrument.expiry_date,
            Instrument.strike,
            Instrument.option_type,
        )
    )
    return list(db.scalars(stmt).all())
