from datetime import date
from decimal import Decimal

from backend.app.instruments.upstox_master import UpstoxInstrumentMaster


def test_maps_equity():
    row = {
        "segment": "NSE_EQ",
        "exchange": "NSE",
        "instrument_type": "EQ",
        "instrument_key": "NSE_EQ|INE002A01018",
        "trading_symbol": "RELIANCE",
        "lot_size": 1,
        "tick_size": 0.05,
    }

    record = UpstoxInstrumentMaster.to_record(row)

    assert record is not None
    assert record.instrument_key == "NSE|NSE_EQ|RELIANCE|EQ|-|-|-"
    assert record.option_type is None


def test_maps_option():
    row = {
        "segment": "NSE_FO",
        "exchange": "NSE",
        "instrument_type": "CE",
        "instrument_key": "NSE_FO|12345",
        "underlying_symbol": "NIFTY",
        "underlying_key": "NSE_INDEX|Nifty 50",
        "trading_symbol": "NIFTY 25000 CE 24 SEP 26",
        "expiry": 178,
        "strike_price": 25000,
        "lot_size": 65,
        "tick_size": 0.05,
    }

    record = UpstoxInstrumentMaster.to_record(row)

    assert record is not None
    assert record.exchange == "NSE"
    assert record.segment == "NSE_FO"
    assert record.option_type == "CE"
    assert record.strike == Decimal("25000")
