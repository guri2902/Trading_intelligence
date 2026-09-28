from datetime import datetime, timedelta, timezone
from backend.app.structure.swings import detect_swings
from backend.app.structure.classifier import label_latest_structure, infer_trend
from backend.app.structure.events import detect_bos_choch
from backend.app.structure.engine import MarketStructureEngine


def make_rows():
    # Clear swing pattern, followed by a confirmed upside break.
    prices = [
        (100, 101, 99, 100),
        (100, 103, 99, 102),
        (102, 105, 101, 104),
        (104, 106, 102, 103),
        (103, 104, 100, 101),
        (101, 103, 99, 102),
        (102, 107, 101, 106),
        (106, 109, 104, 108),
        (108, 110, 106, 109),
        (109, 112, 107, 111),
        (111, 114, 109, 113),
    ]
    start = datetime(2026, 9, 10, 9, 15, tzinfo=timezone.utc)
    return [
        {
            "timestamp": start + timedelta(minutes=i),
            "open": x[0],
            "high": x[1],
            "low": x[2],
            "close": x[3],
            "volume": 1000,
        }
        for i, x in enumerate(prices)
    ]


def test_swings_are_confirmed():
    rows = make_rows()
    swings = detect_swings(rows, left=1, right=1)
    assert swings
    assert all(s["kind"] in {"HIGH", "LOW"} for s in swings)


def test_structure_engine_returns_contract():
    result = MarketStructureEngine(left=1, right=1).analyze(make_rows())
    assert result["swings"]
    assert result["trend"] in {"BULLISH", "BEARISH", "RANGE"}
    assert "support_zones" in result
    assert "resistance_zones" in result
    assert "events" in result


def test_bos_can_be_detected():
    rows = make_rows()
    swings = detect_swings(rows, left=1, right=1)
    events = detect_bos_choch(rows, swings)
    assert any(e["event"] in {"BOS", "CHOCH"} for e in events)
