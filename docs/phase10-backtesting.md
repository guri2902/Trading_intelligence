# Phase 10 — Backtesting Engine

## Purpose

Create a deterministic historical simulator that treats execution costs,
slippage and look-ahead as first-class concerns.

## Core rule

A signal generated at bar `i` is executed on bar `i+1` by default.

The signal callback receives only:
`rows[:i+1]`

It never receives future candles.

## Execution model

Supports:
- directional long/short trades;
- explicit entry;
- structural invalidation;
- TP1/TP2;
- next-bar execution;
- slippage;
- brokerage;
- STT;
- exchange transaction costs;
- GST;
- SEBI charges;
- stamp duty;
- partial fills;
- latency configuration;
- MFE / MAE;
- end-of-data exit.

The monetary charge rates are configurable because they are exchange/broker/jurisdiction dependent and should be loaded from current verified configuration rather than hard-coded into the strategy logic.

## Same-bar ambiguity

When a single OHLC bar touches both stop and target, the backtester assumes the stop happens first.

This is deliberately conservative.

## Metrics

Reports:
- net profit
- return %
- win rate
- gross profit/loss
- profit factor
- expectancy
- maximum drawdown
- maximum drawdown %
- Sharpe
- Sortino
- average win/loss
- largest win/loss

## Underlying vs options

`mode=UNDERLYING` can use underlying OHLC.

`mode=OPTIONS` requires actual historical option prices.

The engine deliberately emits a warning and does not synthesize option P&L from an index candle series.

## Strategy integration

`StrategyBacktestAdapter` connects Phase 9 strategies to the engine through a historical state callback.

Production state generation must calculate indicators/structure/options using only the historical slice visible at that timestamp.

## Current API

`POST /phase10/smoke`

This is a deterministic integration/smoke endpoint.

The production strategy runner will be expanded in the next validation phase.

## Phase gate

Before Phase 11:
- [ ] Connect real Phase 9 strategy state calculation.
- [ ] Backtest actual OptionVault historical option prices.
- [ ] Add option contract expiry/square-off handling.
- [ ] Add spread-aware fills.
- [ ] Add liquidity/partial-fill logic using historical depth when available.
- [ ] Add walk-forward splits.
- [ ] Add out-of-sample reporting.
- [ ] Add baseline comparison.
- [ ] Validate costs against current broker/exchange schedules.
- [ ] Add Monte Carlo/bootstrap stress analysis.
