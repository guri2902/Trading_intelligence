# Phase 7 — Market Structure Engine

## Purpose

Convert deterministic price action into contextual market-structure information.

The engine does not issue a trade signal.

## Swing detection

Confirmed pivots require left/right candle context. This means a swing is not treated as confirmed until its right-side confirmation candles exist.

This is important for backtesting because it prevents using an unconfirmed future pivot as if it were known earlier.

## Structure labels

Highs:
- HH — higher high
- LH — lower high

Lows:
- HL — higher low
- LL — lower low

These are relative structural labels, not standalone trade signals.

## Structural events

The engine detects:
- BOS — Break of Structure
- CHOCH — Change of Character
- breakout
- breakdown
- rejection
- failed breakout

Close-based confirmation is used for breaks instead of treating a single wick as a confirmed structural break.

## Zones

Swing prices are grouped into contextual:
- support zones
- resistance zones

Zones have:
- center
- low
- high
- touch count

This deliberately avoids pretending that support/resistance is always one exact magical price.

## Context states

The output can classify:
- BULLISH
- BEARISH
- RANGE
- TREND
- CONSOLIDATION
- BREAKOUT
- BREAKDOWN
- pullback
- retest
- rejection
- failed breakout

## API

`POST /phase7/structure`

## Downstream use

Phase 7 output becomes an input to:
- options engine;
- strategy engine;
- ML features;
- CE/PE debate;
- contrarian agent;
- risk engine.

It still does not make the final BUY CE / BUY PE / WAIT / NO TRADE decision.

## Phase gate

Before Phase 8:
- [ ] Validate swings against manually marked charts.
- [ ] Test multiple volatility regimes.
- [ ] Test equal highs/lows and overlapping pivots.
- [ ] Add adaptive prominence using ATR.
- [ ] Validate BOS/CHOCH against historical examples.
- [ ] Add stronger zone clustering.
- [ ] Connect structure to real persisted candles.
