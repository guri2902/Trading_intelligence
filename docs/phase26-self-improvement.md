# Phase 26 — Self-Improvement / Evaluation Loop

The system now has a governed improvement loop:

signal -> realized outcome -> agent feedback -> candidate generation ->
historical replay/OOS evaluation -> promotion gate -> immutable version.

## Hard rules

- No LLM or agent can modify production strategy code at runtime.
- Candidate changes are parameter/version candidates, not source rewrites.
- Candidates must beat the baseline on OOS performance and expectancy.
- OOS P&L must remain positive when that gate is enabled.
- Excessive OOS drawdown increase blocks promotion.
- Every candidate and promotion decision is auditable.

Phases 23–25 remain the source of optimization, OOS validation and ML
evaluation. Phase 26 only governs whether a validated candidate becomes the
next immutable strategy version.
