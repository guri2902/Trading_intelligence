from __future__ import annotations

from datetime import date
from decimal import Decimal


def canonical_identity(
    *,
    exchange: str,
    segment: str,
    trading_symbol: str,
    instrument_type: str,
    expiry_date: date | None = None,
    strike: Decimal | None = None,
    option_type: str | None = None,
) -> str:
    """
    Produces a deterministic internal identity.

    Example option:
      NSE|NFO|NIFTY|OPT|2026-09-24|25000|CE

    The Upstox/NSE source key is stored separately as an alias.
    """
    parts = [
        exchange.upper().strip(),
        segment.upper().strip(),
        trading_symbol.upper().strip(),
        instrument_type.upper().strip(),
        expiry_date.isoformat() if expiry_date else "-",
        f"{strike.normalize()}" if strike is not None else "-",
        option_type.upper().strip() if option_type else "-",
    ]
    return "|".join(parts)


def is_option(record) -> bool:
    return record.instrument_type.upper() in {"OPTION", "OPT"} or (
        record.option_type in {"CE", "PE"}
        and record.expiry_date is not None
    )
