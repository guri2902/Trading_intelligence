# Phase 23 — Strategy Optimization

Adds a provider-independent optimization layer above the Phase 21/22
historical options backtesters.

## Design
- Evaluator is injected: optimization never fabricates market data.
- Search space is explicit and finite.
- Objective balances net P&L, expectancy, profit factor, Sharpe,
  Sortino and consistency while penalizing drawdown.
- Minimum-trade and maximum-drawdown feasibility gates prevent
  selecting unstable parameter sets.
- Results preserve trial parameters, metrics, objective and failure reason.
- The API fails closed when no real backtest adapter is provided.

## Optuna compatibility
The optimization contract is deliberately provider-independent so Optuna
can be used as a pluggable sampler/pruner without changing the backtester
or objective semantics in a later integration.
