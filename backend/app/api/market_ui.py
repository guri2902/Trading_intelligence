from __future__ import annotations

from fastapi import APIRouter, Query

from ..market_data_pipeline import MarketDataPipeline


router = APIRouter(
    prefix="/ui/market",
    tags=["ui-market-data"],
)

pipeline = MarketDataPipeline()


@router.get("/snapshot")
def market_snapshot(
    symbol: str = Query("NIFTY"),
    instrument_key: str | None = Query(default=None),
    include_candles: bool = Query(default=True),
    candle_interval: int = Query(default=5, ge=1, le=60),
    candle_limit: int = Query(default=100, ge=1, le=500),
):
    return pipeline.snapshot(
        symbol=symbol,
        instrument_key=instrument_key,
        include_candles=include_candles,
        candle_interval=candle_interval,
        candle_limit=candle_limit,
    )


@router.get("/health")
def market_health():
    provider = pipeline.data_service.providers.get("upstox")

    if provider is None:
        return {
            "provider": "upstox",
            "status": "NOT_REGISTERED",
            "authenticated": False,
        }

    health = getattr(provider, "health", None)
    if health is None:
        return {
            "provider": "upstox",
            "status": "UNKNOWN",
            "authenticated": False,
        }

    result = health().model_dump(mode="json")

    try:
        ltp, timestamp = provider.market_quote("NSE_INDEX|Nifty 50")
        result["market_quote"] = {
            "status": "OK" if ltp is not None else "NO_DATA",
            "ltp": ltp,
            "timestamp": timestamp.isoformat() if timestamp else None,
        }
    except Exception as exc:
        result["market_quote"] = {
            "status": "ERROR",
            "ltp": None,
            "timestamp": None,
            "error": str(exc),
        }

    return result
