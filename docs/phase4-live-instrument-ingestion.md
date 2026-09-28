# Phase 4 — Live Instrument Master + Session Validation

## What changed

Phase 4 connects the canonical database to the current Upstox BOD instrument master.

The official Upstox instruments documentation says:
- BOD contains the instruments available at the beginning of the day;
- JSON is preferred over CSV;
- `instrument_key` is unique and should be preferred over `exchange_token`;
- NSE FO option rows contain expiry, CE/PE type, underlying key/symbol, strike, lot size and tick size.

## Official source

```text
https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz
```

The URL is the live BOD JSON.gz source documented by Upstox.

## Core universe filter

The sync endpoint can be restricted to:
- `NSE_INDEX`
- `NSE_FO`
- INDEX / FUT / CE / PE
- NIFTY / BANKNIFTY related underlyings

This avoids unnecessarily loading every global/BSE/MCX instrument when building the first Indian index-options universe.

## Session semantics

NSE equity derivatives:
- Pre-open: 09:00–09:15 IST
- Regular: 09:15–15:40 IST
- Trade modification: 15:40–16:15 IST
- weekends are closed.

Holiday dates stay external to the hard-coded session clock so the official NSE holiday list can be refreshed without code changes.

## API

### Check current session

```text
GET /phase4/market-session
```

or:

```text
GET /phase4/market-session?timestamp=2026-09-10T10:00:00+05:30
```

### Sync the core index/derivative universe

```text
POST /phase4/instruments/sync-core
```

This downloads the current official Upstox BOD JSON.gz and stores normalized records in the database.

## Safety

- No access token is embedded in the instrument-master URL.
- No live order endpoint is introduced.
- No expired contract is selected by default.
- Source vendor keys are preserved through aliases.
- Raw source data is cached with timestamped filenames.
- Failure to download the master aborts rather than silently using stale data.

## Phase gate

Before Phase 5:
- [ ] Run sync using a real environment.
- [ ] Verify NIFTY index key.
- [ ] Verify BANKNIFTY index key.
- [ ] Verify current futures and CE/PE contracts.
- [ ] Verify current and next expiries.
- [ ] Verify strike and lot-size values against the source.
- [ ] Add refreshed NSE holiday data.
- [ ] Persist raw-master version metadata.
- [ ] Add duplicate/conflict audit.
- [ ] Wire candles and option snapshots to instrument IDs.
