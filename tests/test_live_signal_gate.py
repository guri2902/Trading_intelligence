from datetime import datetime

from backend.app.agents.models import AgentInput
from backend.app.data_gates.live_signal import evaluate_live_signal_gate


def payload(candle="2026-09-11T11:25:00+05:30", option="2026-09-11T11:28:00+05:30"):
    return AgentInput(
        timestamp=candle,
        market={
            "symbol": "NIFTY",
            "data_quality_status": "PASS",
            "stale": False,
            "candle_timestamp": candle,
            "candle_spot": 23398.1,
        },
        options={
            "status": "PASS",
            "snapshot_timestamp": option,
            "underlying_spot": 23398.1,
        },
    )


def test_gate_passes_fresh_open_market_data():
    g = evaluate_live_signal_gate(payload())
    assert g.passed
    assert g.reasons == []
    assert g.freshness_seconds == 180.0


def test_gate_returns_all_reasons():
    g = evaluate_live_signal_gate(
        payload(candle="2026-09-11T15:25:00+05:30", option="2026-09-11T16:18:48.551000+05:30")
    )
    assert not g.passed
    assert any(x.startswith("STALE_DATA:") for x in g.reasons)
    assert any(x.startswith("MARKET_SESSION_CLOSED:") for x in g.reasons)


def test_gate_rejects_spot_divergence():
    p = payload()
    p.options["underlying_spot"] = 23450.0
    g = evaluate_live_signal_gate(p)
    assert not g.passed
    assert any(x.startswith("SPOT_DIVERGENCE:") for x in g.reasons)


def test_gate_rejects_option_snapshot_before_candle():
    g = evaluate_live_signal_gate(
        payload(candle="2026-09-11T11:30:00+05:30", option="2026-09-11T11:28:00+05:30")
    )
    assert not g.passed
    assert "OPTION_SNAPSHOT_BEFORE_LATEST_CANDLE" in g.reasons
