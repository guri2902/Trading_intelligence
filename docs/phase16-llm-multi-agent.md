# Phase 16 — LLM Multi-Agent Critic and CE/PE Debate

Phase 16 adds a real LLM orchestration layer around the deterministic Phase 13/15 agent system.

## Design rule
Deterministic market data, option-chain quality, strategy triggers, risk and QA remain authoritative. LLMs are advisory critics. They cannot bypass a veto or manufacture missing market facts.

## Agent reviews
The LLM layer can review Technical, Options, Strategy, ML, Fundamental, Sentiment, News/Macro and Contrarian agents. Each review records provider, model, request id, latency, evidence, risks and unresolved questions in the existing Phase 15 audit metadata.

## CE/PE debate
A second structured LLM pass challenges the deterministic CE/PE debate, including the contrarian attack. Its winner is advisory only; the persisted deterministic decision remains the actual trade decision.

## API
`GET /phase16/health`

`POST /phase16/agent-run`

The run accepts `data`, optional `research`, and optional `provider`, `model`, and selected `enabled_agents`.

## Safety
No live order placement is introduced. The LLM output is bounded and validated. Missing or malformed LLM recommendations fall back to `NO_TRADE` for the advisory debate rather than changing deterministic execution logic.
