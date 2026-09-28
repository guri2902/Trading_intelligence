# Phase 17 — Signal Fusion, Ranking & Trade Candidate Generation

## Purpose

Phase 17 converts the audited multi-agent research result into ranked directional candidates:

- `BUY_CE`
- `BUY_PE`
- `WAIT`
- `NO_TRADE`

The engine combines deterministic agent scores, the CE/PE debate, strategy evidence, ML/research context and bounded LLM review metadata.

## Source of truth

Deterministic market/data/options/risk/QA gates remain authoritative. LLM reviews can only provide bounded advisory score adjustments and cannot remove a veto or create missing market data.

## Hard gates

A trade cannot be selected when any of the following is present:

- risk veto
- failed QA
- stale market data
- non-passing market data quality
- unavailable/failed option data
- CE/PE debate resolves to `NO_TRADE`
- no eligible option contract
- insufficient signal score or CE/PE separation

## Ranking

The fusion layer uses explicit weights by specialist agent and a 65/35 combination of directional evidence and CE/PE debate strength. Each candidate exposes its score components and evidence for auditability.

## Trade plan

When an eligible option contract is supplied, the candidate includes:

- option type
- strike and expiry
- entry premium
- stop loss
- TP1 / TP2
- risk-reward
- lot size / quantity where provided
- contract source
- invalidation conditions

Contract-level protective defaults are used only when the input contract does not supply explicit SL/TP values. These are planning defaults, not guarantees.

## API

`GET /phase17/health`

`POST /phase17/signal`

The endpoint can run deterministic agents alone or the Phase 16 LLM advisory layer before fusion. Live order execution remains disabled.
