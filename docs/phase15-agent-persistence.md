# Phase 15 — Agent Persistence, Research Integration & Performance Attribution

Phase 15 converts agent analysis from an in-memory decision into an auditable research artifact.

## Added
- Durable `agent_runs` records with decision, confidence, score, debate winner and input hash.
- Per-agent `agent_run_records` containing stance, evidence, risks, questions, metadata, provider/model, prompt hash and result hash.
- `research_snapshots` storing the exact sourced research bundle used for the run.
- `decision_outcomes` for realized direction, P&L, return and exit context.
- `agent_performance` aggregation for directional accuracy, score/confidence averages and useful vetoes.
- `ResearchBundle -> AgentInput` enrichment without changing deterministic market/option fields.
- APIs for creating runs, reading run/audit detail, recording outcomes and viewing agent performance.
- Backward-compatible fix for the Pydantic `schema` field warning in the LLM prompt model.

## Safety
- Live order execution remains disabled.
- Research does not override deterministic market calculations.
- Missing research stays missing; no synthetic fundamentals or sentiment are fabricated.
- Agent and LLM metadata is persisted only as structured audit information; secrets are not stored.

## Endpoints
- `POST /phase15/agent-run`
- `GET /phase15/runs`
- `GET /phase15/runs/{run_id}`
- `POST /phase15/outcomes`
- `GET /phase15/performance`
- `GET /phase15/health`

## Self-improvement hook
The performance table is intentionally descriptive, not self-modifying. Future promotion logic can use these metrics as evidence for walk-forward validation and version gates; agents do not rewrite strategies automatically.
