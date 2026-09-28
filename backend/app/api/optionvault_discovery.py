from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Query

from ..options_backtest.optionvault_loader import OptionVaultLoader

router = APIRouter(prefix="/backtest/optionvault", tags=["OptionVault Discovery"])


def _iso(v: str) -> str:
    return str(v).split("T", 1)[0]


@router.get("/discover")
def discover(
    underlying: str = Query("NIFTY"),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
):
    wanted = underlying.strip().upper()
    contracts = OptionVaultLoader().discover_contracts()
    filtered = []
    for c in contracts:
        symbol = c.underlying_symbol.upper()
        if wanted and wanted not in symbol:
            continue
        first = date.fromisoformat(_iso(c.first_timestamp))
        last = date.fromisoformat(_iso(c.last_timestamp))
        if from_date and last < from_date:
            continue
        if to_date and first > to_date:
            continue
        filtered.append(c)

    expiries = sorted({c.expiry for c in filtered})
    strikes = sorted({float(c.strike) for c in filtered})
    types = sorted({c.option_type for c in filtered})
    by_expiry = {}
    for e in expiries:
        by_expiry[e] = {
            "strikes": sorted({float(c.strike) for c in filtered if c.expiry == e}),
            "option_types": sorted({c.option_type for c in filtered if c.expiry == e}),
            "contracts": [
                {
                    "path": c.path,
                    "strike": float(c.strike),
                    "option_type": c.option_type,
                    "rows": c.rows,
                    "first_timestamp": c.first_timestamp,
                    "last_timestamp": c.last_timestamp,
                }
                for c in filtered if c.expiry == e
            ],
        }

    return {
        "underlying": wanted,
        "contract_count": len(filtered),
        "expiries": expiries,
        "strikes": strikes,
        "option_types": types,
        "by_expiry": by_expiry,
        "data_source": "OptionVault",
        "synthetic_prices": False,
    }
