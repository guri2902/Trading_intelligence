# Phase 12 — ML Engine

## Purpose

Add a supervised ML layer on top of deterministic Phase 6 features.

The ML layer is advisory evidence. It does not override structure, options,
strategy or risk.

## Target

Default:

`y[t] = 1` when future return over N bars is greater than the configured
threshold; otherwise `0`.

The final N observations have unknown outcomes and are never used for training.

## Features

Default input features:
- EMA 9/20/50
- RSI 14
- ATR 14
- VWAP distance
- relative volume
- returns
- momentum
- volatility
- PDH/PDL/PDC distances

## Models

Current candidates:
- Logistic Regression
- Random Forest
- HistGradientBoosting

The system is structured so XGBoost/LightGBM/Kronos can be added later after
independent validation rather than assuming a complex model is automatically
better.

## Chronology

The first implementation uses:

`TRAIN -> TEST`

with no shuffle.

The next research integration should place this inside the Phase 11
walk-forward pipeline:

`TRAIN -> CALIBRATION/VALIDATION -> OOS`

## Evaluation

Reports:
- accuracy
- balanced accuracy
- precision
- recall
- F1
- ROC AUC
- Brier score
- log loss
- feature importance

Balanced accuracy and probability-quality metrics are retained so raw accuracy
does not dominate model selection.

## Prediction

Each prediction carries:
- model name
- probability up/down
- predicted class
- confidence
- feature version
- training end timestamp

This creates an audit trail showing what data the model could have known.

## Calibration

A separate calibration utility is included. Calibration should use a dedicated
chronological calibration slice rather than reusing the OOS test set.

## API

`POST /phase12/train`

## Promotion rule

A better ML metric does not automatically become the final signal.

The eventual decision stack remains:

data → features → structure → options → strategies → ML → agents → risk → final decision.

## Phase gate

Before Phase 13:
- [ ] Connect ML training to Phase 11 walk-forward splits.
- [ ] Add dedicated calibration slice.
- [ ] Add OOS probability tracking.
- [ ] Compare against logistic and naive baselines.
- [ ] Add XGBoost/LightGBM only if validated.
- [ ] Validate feature leakage rigorously.
- [ ] Store model artifacts/version metadata.
- [ ] Add drift monitoring.
- [ ] Only then expose ML predictions to the agent debate layer.
