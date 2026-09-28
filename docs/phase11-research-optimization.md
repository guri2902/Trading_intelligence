# Phase 11 — Walk-Forward + Optimization + Promotion Gates

## Goal

Turn backtesting into a research process instead of simply maximizing historical P&L.

## Walk-forward

The splitter is strictly chronological:

`TRAIN -> VALIDATION -> OOS TEST`

Then the window advances.

There is:
- no shuffle;
- no random cross-validation;
- no future leakage.

Expanding or rolling training windows are supported.

## Optimization

An optional `OptunaOptimizer` wrapper provides:
- integer search;
- float search;
- categorical search;
- seeded TPE sampler;
- configurable trial count;
- deterministic parameter capture.

The optimizer searches parameter space; it does not automatically promote the best historical parameter set.

## Research score

The research score combines:
- profit factor
- expectancy
- Sharpe
- Sortino
- return
- win rate
- drawdown

It also supports minimum-trade and minimum-profit-factor gates.

A high return with tiny sample size can therefore fail the gate.

## Baselines

Two simple benchmark foundations are provided:
- buy-and-hold;
- naive EMA.

The real research report should compare each strategy against these and other simple baselines.

## Promotion gate

A candidate cannot be promoted merely because in-sample P&L is high.

The promotion gate requires:
- positive validation score;
- controlled OOS degradation;
- regime robustness;
- baseline outperformance;
- paper validation.

The gate is fail-closed.

## Important

Optimization is not yet connected to automatic parameter mutation of production strategy classes. That separation is intentional.

The self-improving system will work as:

signal → outcome → evaluation → research candidate → walk-forward/OOS → promotion gate → new version

rather than allowing an LLM to silently rewrite trading logic.

## API

`POST /phase11/walk-forward/plan`

`POST /phase11/promotion-gate`

## Phase gate

Before Phase 12:
- [ ] Connect Optuna to real Phase 9 strategy parameters.
- [ ] Run real OptionVault historical datasets.
- [ ] Produce train/validation/OOS reports.
- [ ] Add regime-level performance.
- [ ] Add baseline leaderboard.
- [ ] Add parameter stability analysis.
- [ ] Add Monte Carlo/stress tests.
- [ ] Store research runs and versions in PostgreSQL.
- [ ] Only then expose candidate strategies to the agent layer.
