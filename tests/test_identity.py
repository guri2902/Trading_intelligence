from datetime import date
from decimal import Decimal

from backend.app.instruments.identity import canonical_identity


def test_option_identity_is_deterministic():
    value = canonical_identity(
        exchange="nse",
        segment="nfo",
        trading_symbol="NIFTY",
        instrument_type="OPT",
        expiry_date=date(2026, 9, 24),
        strike=Decimal("25000"),
        option_type="ce",
    )
    assert value == "NSE|NFO|NIFTY|OPT|2026-09-24|2.5E+4|CE"


def test_underlying_identity_is_stable():
    value = canonical_identity(
        exchange="nse",
        segment="index",
        trading_symbol="NIFTY 50",
        instrument_type="INDEX",
    )
    assert value == "NSE|INDEX|NIFTY 50|INDEX|-|-|-"
