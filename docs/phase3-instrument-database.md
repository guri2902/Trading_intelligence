# Phase 3 — Instrument Master + Canonical Database

## Objective

Introduce a single instrument identity and persistence layer before any strategy or AI layer is built.

## Canonical identity

Examples:

- Index:
  `NSE|INDEX|NIFTY 50|INDEX|-|-|-`

- Option:
  `NSE|NFO|NIFTY|OPT|2026-09-24|25000|CE`

Vendor/source keys are kept separately as `instrument_aliases`, so Upstox/NSE/other feeds can map to one internal instrument.

## Tables

### `instruments`
Canonical instrument metadata:
exchange, segment, instrument type, symbol, underlying, expiry, strike, option type, lot size, tick size, active status, source.

### `instrument_aliases`
Maps vendor source keys to canonical instruments.

### `candles`
Normalized OHLCV/OI history with timeframe, timestamp, source and quality status.

### `market_snapshots`
Normalized point-in-time quote/option-chain values.

### `data_quality_events`
Persistent audit trail for stale data, gaps, duplicates, malformed data and other provider-quality problems.

## Design rule

All later modules should use `instrument_id` / canonical identity, not raw vendor symbols.

This prevents:
- CE/PE mixups;
- expiry mismatch;
- stale contract selection;
- vendor-specific key leakage;
- cross-provider symbol collisions.

## API

### Health

`GET /health`

### Sync instruments

`POST /instruments/sync`

### Query master

`GET /instruments?exchange=NSE&segment=NFO&underlying_symbol=NIFTY&option_type=CE`

## Database

Development defaults to SQLite.

Production environment should use PostgreSQL:

```text
DATABASE_URL=postgresql+psycopg://...
```

A Docker Compose PostgreSQL service is included.

## Phase 3 gate

Before moving to Phase 4:

- [ ] Download/provider instrument master from Upstox.
- [ ] Map real NIFTY/BANKNIFTY/index/stock contracts.
- [ ] Persist aliases.
- [ ] Verify expiries dynamically.
- [ ] Verify strike increments and lot sizes from source data.
- [ ] Detect duplicate/conflicting identities.
- [ ] Persist normalized candles/quotes against `instrument_id`.
- [ ] Record data-quality events.
- [ ] Validate session/timezone semantics.

No signals or live orders are introduced in this phase.
