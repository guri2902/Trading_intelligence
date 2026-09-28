# Phase 9 — Strategy Engine

## Purpose

Run multiple independent strategy families against the same deterministic market state.

The engine generates candidates. It does not decide the final BUY CE / BUY PE / WAIT / NO TRADE output.

## Included strategies

1. VWAP Pullback
2. EMA Trend Continuation
3. Opening Range Breakout (ORB)
4. ORB Retest
5. Support/Resistance Rejection
6. Range Fade
7. Momentum Continuation
8. Volatility Breakout
9. Option Directional candidate

Each strategy returns:
- direction;
- state;
- entry;
- invalidation;
- TP1;
- TP2;
- R:R;
- confidence;
- evidence;
- wait conditions;
- invalidation reasons;
- metadata.

## Strategy independence

Each strategy is implemented separately so it can later be:
- backtested independently;
- optimized independently;
- disabled independently;
- benchmarked by regime;
- assigned different weights;
- compared against baselines.

The engine does not average strategy signals blindly.

## Risk semantics

Strategy stop levels are structural/ATR-derived candidates only. The later Risk Engine is authoritative for final stop, size, daily limits and trade eligibility.

## Option-specific strategy

The option strategy reads the Phase 8 CE/PE comparison and can produce a BUY_CE / BUY_PE expression candidate, but it still requests:
- underlying strategy confirmation;
- risk approval.

This prevents the option chain alone from becoming the final signal.

## API

`POST /phase9/strategies/evaluate`

## No-trade behavior

A neutral market can result in zero triggered strategies. This is intentional and preferred over forcing a trade.

## Phase gate

Before Phase 10:
- [ ] Run every strategy on real historical data.
- [ ] Create independent performance metrics.
- [ ] Add regime-specific strategy attribution.
- [ ] Compare against naive baselines.
- [ ] Add strategy version IDs.
- [ ] Add transaction-cost-aware evaluation.
- [ ] Connect strategy candidates to the backtest engine.
