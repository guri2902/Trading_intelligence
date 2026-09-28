# Phase 5 — Durable Market Data + Quality Gate

## Goal

Turn normalized provider responses into persistent, auditable data that downstream calculations can safely consume.

## Pipeline

Provider → normalization → quality evaluation → canonical instrument mapping → persistence → latest-data query.

## Storage

The Phase 3 schema is now used for:
- `candles`
- `market_snapshots`
- `data_quality_events`

Each record retains source, timestamp and quality status.

## Candle ingestion

`POST /phase5/ingest/candles`

The endpoint:
1. resolves the canonical instrument;
2. fetches candles from the selected provider;
3. evaluates OHLC structure, duplicates, gaps and staleness;
4. upserts the rows;
5. records a quality event when checks fail.

Upstox V3 supports customizable candle intervals and returns timestamp, OHLC, volume and OI in its candle array. The provider remains responsible for respecting API retrieval limits. 

## Option-chain ingestion

`POST /phase5/ingest/option-chain`

The endpoint:
1. fetches a live option-chain snapshot;
2. maps each expiry/strike/CE-PE contract to the canonical instrument;
3. evaluates staleness, duplicates, malformed bid/ask and missing LTP;
4. persists the snapshot;
5. records an audit event when signal safety is compromised.

Upstox's option-chain endpoint requires the underlying instrument key and an expiry date. 

## Signal safety

`signal_safe=false` means the later signal engine must not use that data as authoritative input.

Examples:
- stale data;
- duplicate contracts;
- malformed OHLC;
- missing complete option chain;
- unmapped contracts.

WARN conditions are retained for analysis but should be handled explicitly by the downstream risk/data-quality gate.

## New endpoints

- `POST /phase5/ingest/candles`
- `POST /phase5/ingest/option-chain`
- `GET /phase5/candles/latest`

## Important

No AI, indicators, strategies, backtests, ranking or trading execution are introduced yet. This phase only makes the market data trustworthy and persistent.

## Phase gate

Before Phase 6:
- [ ] Run a real Upstox candle ingestion.
- [ ] Run a real option-chain ingestion for NIFTY and BANKNIFTY.
- [ ] Confirm canonical instrument mapping is complete.
- [ ] Confirm no duplicate persistence occurs on repeated ingestion.
- [ ] Confirm stale snapshots become signal-unsafe.
- [ ] Confirm quality events are visible and queryable.
- [ ] Confirm timestamps remain UTC internally and IST at presentation boundaries.
