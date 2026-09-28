from datetime import datetime, timezone, timedelta

from backend.app.storage.quality import evaluate_candles, evaluate_option_quotes


def test_candles_pass():
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(3):
        ts = now - timedelta(minutes=2-i)
        rows.append({
            "timestamp": ts.isoformat(),
            "open": 100+i,
            "high": 102+i,
            "low": 99+i,
            "close": 101+i,
            "volume": 1000,
        })

    result = evaluate_candles(rows, timeframe_minutes=1)
    assert result.status in {"PASS", "WARN"}
    assert result.malformed_count == 0


def test_option_chain_duplicates_fail():
    now = datetime.now(timezone.utc)
    rows = [
        {
            "instrument_key": "OPT1",
            "expiry": "2026-09-24",
            "strike": 25000,
            "option_type": "CE",
            "ltp": 100,
            "bid": 99,
            "ask": 101,
        },
        {
            "instrument_key": "OPT1",
            "expiry": "2026-09-24",
            "strike": 25000,
            "option_type": "CE",
            "ltp": 100,
            "bid": 99,
            "ask": 101,
        },
    ]
    result = evaluate_option_quotes(
        rows,
        snapshot_timestamp=now,
    )
    assert result.status == "FAIL"
    assert result.duplicate_count == 1
    assert result.signal_safe is False
