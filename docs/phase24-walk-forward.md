# Phase 24 — Walk-Forward / Out-of-Sample Validation

This phase prevents optimized strategy parameters from being promoted based
only on in-sample performance.

## Windowing
For each chronological window:
1. Optimizer receives only the training slice.
2. Parameters are frozen.
3. Backtester receives only the following unseen test slice.
4. Test metrics are stored separately.
5. The process rolls forward without peeking into future rows.

## Promotion gates
A model/strategy is eligible only when:
- enough OOS windows are valid,
- minimum OOS trade count is met,
- optional win-rate/drawdown gates pass,
- the required percentage of OOS windows are profitable.

This phase does not invent market results and does not override the
deterministic backtester or risk engine.
