
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text

from backend.app.options.models import OptionContract, OptionQuoteState
from backend.app.options.engine import OptionsEngine


DB_URL = "sqlite:///./trading_intelligence.db"


def run():
    engine = create_engine(DB_URL)

    with engine.connect() as conn:

        latest = conn.execute(
            text("""
                SELECT MAX(m.timestamp)
                FROM market_snapshots m
                JOIN instruments i ON i.id = m.instrument_id
                WHERE i.underlying_symbol = 'NIFTY'
                  AND m.source = 'upstox'
                  AND i.option_type IN ('CE', 'PE')
            """)
        ).scalar_one()

        if latest is None:
            raise RuntimeError("No NIFTY option snapshot found.")

        print("LATEST OPTION SNAPSHOT:", latest)

        rows = conn.execute(
            text("""
                SELECT
                    m.timestamp,
                    m.underlying_ltp,
                    m.ltp,
                    m.bid,
                    m.ask,
                    m.bid_qty,
                    m.ask_qty,
                    m.volume,
                    m.open_interest,
                    m.change_in_oi,
                    m.iv,
                    m.delta,
                    m.gamma,
                    m.theta,
                    m.vega,
                    m.rho,

                    i.instrument_key,
                    i.underlying_key,
                    i.underlying_symbol,
                    i.expiry_date,
                    i.strike,
                    i.option_type,
                    i.lot_size,
                    i.tick_size

                FROM market_snapshots m
                JOIN instruments i
                  ON i.id = m.instrument_id

                WHERE i.underlying_symbol = 'NIFTY'
                  AND m.source = 'upstox'
                  AND i.option_type IN ('CE', 'PE')
                  AND m.timestamp = :timestamp

                ORDER BY i.strike, i.option_type
            """),
            {"timestamp": latest},
        ).fetchall()

    if not rows:
        raise RuntimeError("No rows found for latest NIFTY option snapshot.")

    missing_spot = sum(
        1 for r in rows
        if r.underlying_ltp is None
    )

    print("ROWS:", len(rows))
    print("ROWS WITH SNAPSHOT SPOT:", len(rows) - missing_spot)
    print("ROWS MISSING SNAPSHOT SPOT:", missing_spot)

    quotes = []

    for r in rows:

        previous_oi = None

        if (
            r.change_in_oi is not None
            and r.open_interest is not None
        ):
            previous_oi = (
                float(r.open_interest)
                - float(r.change_in_oi)
            )

        contract = OptionContract(
            instrument_key=r.instrument_key,
            underlying_key=r.underlying_key or "",
            underlying_symbol=r.underlying_symbol or "NIFTY",
            expiry=r.expiry_date,
            strike=float(r.strike),
            option_type=r.option_type,
            lot_size=r.lot_size,
            tick_size=(
                float(r.tick_size)
                if r.tick_size is not None
                else None
            ),
        )

        quote = OptionQuoteState(
            contract=contract,
            timestamp=r.timestamp,

            underlying_spot=(
                float(r.underlying_ltp)
                if r.underlying_ltp is not None
                else None
            ),

            ltp=(
                float(r.ltp)
                if r.ltp is not None
                else None
            ),

            bid=(
                float(r.bid)
                if r.bid is not None
                else None
            ),

            ask=(
                float(r.ask)
                if r.ask is not None
                else None
            ),

            bid_qty=r.bid_qty,
            ask_qty=r.ask_qty,

            volume=(
                float(r.volume)
                if r.volume is not None
                else None
            ),

            open_interest=(
                float(r.open_interest)
                if r.open_interest is not None
                else None
            ),

            previous_oi=previous_oi,

            iv=(
                float(r.iv)
                if r.iv is not None
                else None
            ),

            delta=(
                float(r.delta)
                if r.delta is not None
                else None
            ),

            gamma=(
                float(r.gamma)
                if r.gamma is not None
                else None
            ),

            theta=(
                float(r.theta)
                if r.theta is not None
                else None
            ),

            vega=(
                float(r.vega)
                if r.vega is not None
                else None
            ),

            rho=(
                float(r.rho)
                if r.rho is not None
                else None
            ),
        )

        quotes.append(quote)

    print("QUOTES LOADED:", len(quotes))

    print(
        "EXPIRIES:",
        sorted({
            q.contract.expiry.isoformat()
            for q in quotes
        }),
    )

    print(
        "STRIKES:",
        len({
            q.contract.strike
            for q in quotes
        }),
    )

    print(
        "CE:",
        sum(
            q.contract.option_type == "CE"
            for q in quotes
        ),
    )

    print(
        "PE:",
        sum(
            q.contract.option_type == "PE"
            for q in quotes
        ),
    )

    spot_values = {
        q.underlying_spot
        for q in quotes
        if q.underlying_spot is not None
    }

    print("SNAPSHOT SPOTS:", sorted(spot_values))

    result = OptionsEngine().analyze(
        quotes,
        now=quotes[0].timestamp,
    )

    print("\n========== PHASE 8 RESULT ==========")

    print("STATUS:", result["status"])
    print("UNDERLYING:", result.get("underlying_symbol"))
    print("EXPIRY:", result.get("expiry"))
    print("ATM:", result.get("atm_strike"))

    print("\nBEST CE:")
    print(result.get("best_ce"))

    print("\nBEST PE:")
    print(result.get("best_pe"))

    print("\nDEBATE:")
    print(result.get("debate"))

    print("\nTOP CE CANDIDATES:")

    for item in result.get("ce", [])[:5]:
        q = item["quote"]
        m = item["metrics"]

        print(
            "Strike=", q["contract"]["strike"],
            "LTP=", q["ltp"],
            "OI=", q["open_interest"],
            "IV=", q["iv"],
            "Delta=", q["delta"],
            "Gamma=", q["gamma"],
            "Theta=", q["theta"],
            "Vega=", q["vega"],
            "Rho=", q["rho"],
            "Spread=", m["spread"],
            "SpreadPct=", m["spread_pct"],
            "OIChange=", m["oi_change"],
            "Intrinsic=", m["intrinsic_value"],
            "Extrinsic=", m["extrinsic_value"],
            "Liquidity=", m["liquidity_score"],
            "Quality=", m["quality_score"],
            "Eligible=", item["eligible"],
            "Rank=", item["rank_score"],
            "Reasons=", item["rejection_reasons"],
        )

    print("\nTOP PE CANDIDATES:")

    for item in result.get("pe", [])[:5]:
        q = item["quote"]
        m = item["metrics"]

        print(
            "Strike=", q["contract"]["strike"],
            "LTP=", q["ltp"],
            "OI=", q["open_interest"],
            "IV=", q["iv"],
            "Delta=", q["delta"],
            "Gamma=", q["gamma"],
            "Theta=", q["theta"],
            "Vega=", q["vega"],
            "Rho=", q["rho"],
            "Spread=", m["spread"],
            "SpreadPct=", m["spread_pct"],
            "OIChange=", m["oi_change"],
            "Intrinsic=", m["intrinsic_value"],
            "Extrinsic=", m["extrinsic_value"],
            "Liquidity=", m["liquidity_score"],
            "Quality=", m["quality_score"],
            "Eligible=", item["eligible"],
            "Rank=", item["rank_score"],
            "Reasons=", item["rejection_reasons"],
        )

    print("\n====================================")


if __name__ == "__main__":
    run()