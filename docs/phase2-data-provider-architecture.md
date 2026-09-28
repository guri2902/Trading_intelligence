# Phase 2 — Data Provider & Normalization Layer

## Goal

Create one provider boundary for live/historical market data without letting a data vendor leak vendor-specific schemas into the signal engine.

## Provider roles

| Provider | Role | Authority |
|---|---|---|
| Upstox | Primary live market/option-chain + historical API | Primary when configured |
| NSE | Official exchange reference/option-chain surface | Reference / fallback where legally and technically available |
| OptionVault | Historical Indian market research datasets | Historical research |
| OpenBB | Optional multi-provider research connector | Supplemental |
| TradingView MCP | Optional chart context / screenshots / analysis | Supplemental only |

## Fail-closed rules

1. Missing or stale option-chain data must not create a trade.
2. No fabricated fallback prices.
3. No silent mixing of datasets.
4. Provider/source and timestamp travel with every normalized object.
5. Instrument mapping will become a dedicated registry in the next phase.
6. TradingView is never the authoritative feed in this architecture.

## Upstox endpoints used

- V3 Historical Candle API for OHLC data.
- V2 option-chain endpoint for option-chain snapshots.
- V2 option-contract endpoint for contract discovery.

The provider keeps the bearer token server-side and never returns it through API responses.

## Normalization

Candles are:
- converted to timezone-aware UTC;
- de-duplicated by timestamp;
- sorted chronologically;
- rejected when OHLC relationships are malformed.

Option-chain snapshots receive a deterministic quality report covering:
- age/staleness;
- duplicate contracts;
- missing LTP;
- wide bid/ask spreads;
- overall signal-engine eligibility.

## What is intentionally not done yet

- No live order placement.
- No trading signal generation.
- No indicator calculation.
- No strategy logic.
- No AI/LLM calls.
- No NSE CAPTCHA/security bypass.
- No automatic credentials acquisition.

Those belong to later phases and remain disabled until data quality is proven.

## Run

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Health:

```text
GET /health
```

Historical:

```text
GET /market/candles?provider=upstox&instrument_key=NSE_INDEX%7CNifty%2050&unit=minutes&interval=5&from_date=2026-09-09&to_date=2026-09-10
```

Option chain:

```text
GET /option-chain?provider=upstox&underlying_key=NSE_INDEX%7CNifty%2050
```

## Verification gates

Before Phase 3:
- [ ] Upstox token configured in environment only.
- [ ] Real NIFTY/BANKNIFTY candle response parsed.
- [ ] Real option-chain response parsed.
- [ ] Duplicate/gap/staleness checks pass.
- [ ] Instrument keys are persisted and versioned.
- [ ] Market session and timezone normalization is tested.
- [ ] No live execution path is enabled.
