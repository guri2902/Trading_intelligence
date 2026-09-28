from datetime import date, datetime, timezone, timedelta
from backend.app.options.metrics import intrinsic_value, extrinsic_value, spread_metrics
from backend.app.options.engine import OptionsEngine
from backend.app.options.models import OptionContract, OptionQuoteState


def make_quote(option_type, strike, ltp, oi=100000, volume=200000):
    contract=OptionContract(
        instrument_key=f"NSE_FO|{option_type}|{strike}",
        underlying_key="NSE_INDEX|Nifty 50",
        underlying_symbol="NIFTY",
        expiry=date(2026,9,24),
        strike=strike,
        option_type=option_type,
        lot_size=65,
        tick_size=0.05,
    )
    return OptionQuoteState(
        contract=contract,
        timestamp=datetime.now(timezone.utc),
        underlying_spot=25000,
        ltp=ltp,
        bid=ltp-1,
        ask=ltp+1,
        bid_qty=5000,
        ask_qty=5000,
        volume=volume,
        open_interest=oi,
        previous_oi=oi-1000,
        iv=0.15,
        delta=0.5 if option_type=="CE" else -0.5,
        gamma=0.001,
        theta=-10,
        vega=8,
        rho=1,
    )


def test_intrinsic_and_extrinsic():
    assert intrinsic_value(25100,25000,"CE")==100
    assert intrinsic_value(24900,25000,"PE")==100
    assert extrinsic_value(120,25100,25000,"CE")==20


def test_spread_metrics():
    spread, pct = spread_metrics(99,101,100)
    assert spread == 2
    assert pct == 0.02


def test_options_engine_selects_both_sides():
    quotes=[
        make_quote("CE",24900,180),
        make_quote("CE",25000,140),
        make_quote("PE",25000,135),
        make_quote("PE",25100,180),
    ]
    result=OptionsEngine().analyze(
        quotes,
        preferred_expiry=date(2026,9,24),
        now=datetime(2026,9,10,tzinfo=timezone.utc),
        atm_distance=150,
    )
    assert result["status"]=="OK"
    assert result["atm_strike"]==25000
    assert result["best_ce"] is not None
    assert result["best_pe"] is not None
    assert result["debate"]["winner"] in {"CE","PE","NO_TRADE"}
