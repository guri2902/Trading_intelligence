# Phase 14 — Research Data + LLM Provider Layer

## Research data

OpenBB is integrated as an optional research connector.

The current OpenBB platform exposes a unified Python interface and provider
extensions, with separate provider modules so data sources can be added/removed
without changing core components.

This phase uses:
- company fundamentals;
- company news;
- macro/economic indicator scaffolding.

OpenBB is not the authoritative live option/price source.

## Source attribution

Fundamental/news objects carry:
- source;
- source type;
- provider;
- retrieval timestamp;
- URL where available;
- confidence.

The goal is to prevent agents from receiving unattributed research facts.

## Sentiment

A small transparent keyword baseline is included only as a fallback.

It is explicitly labeled as a baseline and does not pretend to be a validated
market sentiment model.

Later it can be replaced by:
- a validated transformer;
- provider-native sentiment;
- an LLM classifier with benchmark/OOS validation.

## LLM provider abstraction

Supported interfaces:
- Gemini
- generic OpenAI-compatible endpoint

The provider interface means agent logic does not depend on one vendor SDK.

Gemini's current API exposes `generateContent`, JSON mode, system instructions,
and Python support through the Google GenAI SDK.

## Structured-only LLM input

The LLM receives:
- task;
- structured market/research state;
- explicit schema;
- constraints.

It does not receive:
- raw database dumps;
- credentials;
- arbitrary provider responses without normalization.

## LLM safety rules

The prompt builder requires:
- no invented facts;
- no overriding deterministic calculations;
- no guaranteed-profit language;
- explicit uncertainty;
- JSON output.

LLM output remains opinion/evidence interpretation.

Critical numeric values continue to come from:
- market data;
- option-chain provider;
- deterministic feature engine;
- strategy engine;
- risk engine.

## APIs

- `GET /phase14/health`
- `POST /phase14/openbb/research`
- `POST /phase14/sentiment/aggregate`
- `POST /phase14/llm/research`

## Current limitation

This phase provides connectors and abstraction, but does not automatically
attach LLM opinions to live trading decisions yet.

That connection will be validated in the next phase alongside persistent
agent-run/audit storage.

## Phase gate

Before Phase 15:
- [ ] Configure real OpenBB providers.
- [ ] Verify source/license suitability for each data source.
- [ ] Add historical sentiment evaluation.
- [ ] Add news deduplication and event-impact model.
- [ ] Validate LLM structured-output parsing across providers.
- [ ] Persist prompts/results/model versions.
- [ ] Add agent latency/cost tracking.
- [ ] Connect research outputs into Phase 13.
