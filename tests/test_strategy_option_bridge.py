from backend.app.options_backtest.strategy_option_bridge import select_contract
from backend.app.options_backtest.optionvault_loader import OptionVaultContract
from datetime import datetime


def test_selects_ce_nearest_strike():
    ts1 = "2026-09-01T09:15:00+05:30"
    ts2 = "2026-09-01T15:30:00+05:30"
    contracts = [
        OptionVaultContract("a.csv", "NIFTY", "2026-09-15", 25000, "CE", 10, ts1, ts2),
        OptionVaultContract("b.csv", "NIFTY", "2026-09-15", 25100, "CE", 10, ts1, ts2),
        OptionVaultContract("c.csv", "NIFTY", "2026-09-15", 25000, "PE", 10, ts1, ts2),
    ]
    out = select_contract(
        contracts,
        signal_time=datetime.fromisoformat("2026-09-01T10:00:00+05:30"),
        direction="LONG",
        expiry="2026-09-15",
        strike_reference=25040,
    )
    assert out.option_type == "CE"
    assert out.strike == 25000


def test_short_maps_to_pe():
    ts = "2026-09-01T09:15:00+05:30"
    contracts = [OptionVaultContract("p.csv", "NIFTY", "2026-09-15", 25000, "PE", 10, ts, ts)]
    out = select_contract(
        contracts,
        signal_time=datetime.fromisoformat(ts),
        direction="SHORT",
        strike_reference=25000,
    )
    assert out.option_type == "PE"
