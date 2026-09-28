from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.models import Base
from backend.app.instruments.models import InstrumentRecord
from backend.app.instruments.repository import sync_records


def test_instrument_sync_roundtrip():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    record = InstrumentRecord(
        instrument_key="raw-upstox-key",
        exchange="NSE",
        segment="NFO",
        instrument_type="OPT",
        trading_symbol="NIFTY",
        underlying_symbol="NIFTY",
        expiry_date=date(2026, 9, 24),
        strike=Decimal("25000"),
        option_type="CE",
        lot_size=65,
        tick_size=Decimal("0.05"),
        source="upstox",
        source_updated_at=datetime.now(timezone.utc),
    )

    with Session(engine) as db:
        assert sync_records(db, [record]) == 1
