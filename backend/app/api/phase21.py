from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from .phase21_models import OptionsBacktestRequest, OptionVaultBacktestRequest
from ..options_backtest.engine import HistoricalOptionsBacktestEngine
from ..options_backtest.models import HistoricalOptionBar
from ..providers.optionvault import OptionVaultProvider

router = APIRouter(prefix="/phase21", tags=["phase21"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "phase": 21,
        "mode": "historical_options_backtest",
        "uses_actual_option_prices": True,
        "live_execution": False,
    }


@router.post("/backtest")
def backtest(req: OptionsBacktestRequest):
    return HistoricalOptionsBacktestEngine().run(
        req.bars,
        lambda ctx: req.signal,
        strategy_name=req.strategy_name,
        config=req.config,
    ).model_dump()


@router.post("/backtest/optionvault")
def backtest_optionvault(req: OptionVaultBacktestRequest):
    provider = OptionVaultProvider()

    raw_rows = provider.option_series(
        req.symbol,
        expiry=req.expiry,
        strike=req.strike,
        side=req.side,
        from_date=req.from_date,
        to_date=req.to_date,
    )

    bars = [
        HistoricalOptionBar(
            timestamp=datetime.fromisoformat(str(row["timestamp"])),
            contract_key=str(row.get("symbol") or req.symbol),
            underlying_symbol=str(row.get("name") or "NIFTY"),
            expiry=str(row["expiry"])[:10],
            strike=float(row["strike"]),
            option_type=str(row.get("side") or row.get("option_type")).upper(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(row["volume"]) if row.get("volume") not in (None, "") else None,
            open_interest=int(row["oi"]) if row.get("oi") not in (None, "") else None,
            bid=None,
            ask=None,
        )
        for row in raw_rows
    ]
    unique_bars = {}
    for bar in bars:
        key = (bar.contract_key, bar.timestamp)
        unique_bars[key] = bar

    bars = sorted(
        unique_bars.values(),
        key=lambda x: x.timestamp,
    )
    if not bars:
        raise ValueError("NO_OPTIONVAULT_DATA")

    return HistoricalOptionsBacktestEngine().run(
        bars,
        lambda ctx: req.signal,
        strategy_name=req.strategy_name,
        config=req.config,
    ).model_dump()
    