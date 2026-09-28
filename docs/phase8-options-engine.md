# Phase 8 — Options Engine

## Purpose

Transform raw option-chain quotes into quality-controlled CE/PE candidates.

The engine is deterministic and does not issue a final trade signal.

## Inputs

For every option contract:
- instrument key
- underlying key/symbol
- expiry
- strike
- CE/PE
- LTP
- bid/ask
- bid/ask quantity
- volume
- OI
- previous OI
- IV
- Delta
- Gamma
- Theta
- Vega
- Rho
- underlying spot

These fields match the current Upstox option-chain response structure, where CE/PE contain market data and option Greeks. The live market-data feed also exposes bid/ask depth and Greeks. 

## Calculated values

### Intrinsic / extrinsic
- CE intrinsic = max(spot - strike, 0)
- PE intrinsic = max(strike - spot, 0)
- extrinsic = premium - intrinsic

### Liquidity
A normalized 0–100 ranking using:
- volume
- OI
- bid/ask spread

This is a ranking metric, not a probability of execution.

### Quality
Considers:
- LTP availability
- bid/ask availability
- IV availability
- Greek availability
- spread quality

### Contract selection
The engine:
1. dynamically selects an available non-expired expiry;
2. finds the nearest ATM strike from underlying spot;
3. ranks CE and PE independently;
4. rejects wide-spread, missing-data and low-liquidity contracts;
5. compares the best eligible CE and PE.

It explicitly does **not** choose the cheapest premium automatically.

## CE/PE debate

The output contains:
- CE candidate
- PE candidate
- CE score
- PE score
- winner: CE / PE / NO_TRADE

The comparison remains contract-quality focused. Directional market interpretation will come later from structure, strategies, ML and agents.

## Upstox source

Upstox's current option-chain API documents expiry, strike, underlying spot, instrument keys, market data, OI, bid/ask and option Greeks. The option-contract API supports expiry-specific contract discovery. 

## API

`POST /phase8/options/analyze`

## Phase gate

Before Phase 9:
- [ ] Use real Upstox option-chain responses.
- [ ] Map every returned option to the canonical instrument master.
- [ ] Verify current expiries dynamically.
- [ ] Validate strike increments and lot sizes from master data.
- [ ] Handle missing Greeks explicitly.
- [ ] Add implied-volatility regime and IV percentile.
- [ ] Add PCR and strike-level OI concentration.
- [ ] Add expected-move calculations.
- [ ] Connect option candidates to market structure.
