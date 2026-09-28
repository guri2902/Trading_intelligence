from datetime import datetime, timezone

from backend.app.normalization import normalize_candles, candle_quality_report
from backend.app.providers.base import Candle


def c(ts: str, price: float) -> Candle:
    return Candle(
        instrument_key="NSE_INDEX|Nifty 50",
        timestamp=datetime.fromisoformat(ts),
        open=price,
        high=price + 2,
        low=price - 2,
        close=price + 1,
        volume=100,
        source="test",
    )


def test_deduplicates_and_sorts():
    candles = [
        c("2026-09-10T09:15:00+00:00", 101),
        c("2026-09-10T09:20:00+00:00", 102),
        c("2026-09-10T09:15:00+00:00", 101.5),
    ]
    result = normalize_candles(candles)
    assert len(result) == 2
    assert result[0].timestamp < result[1].timestamp


def test_quality_report():
    candles = [
        c("2026-09-10T09:15:00+00:00", 101),
        c("2026-09-10T09:20:00+00:00", 102),
    ]
    report = candle_quality_report(candles, expected_interval_minutes=5)
    assert report["count"] == 2
    assert report["duplicates"] == 0
