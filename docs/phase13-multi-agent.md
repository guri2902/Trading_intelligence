# Phase 13 — Multi-Agent Intelligence Layer

## Architecture

The first production-oriented agent layer contains:

1. DATA
2. TECHNICAL
3. OPTIONS
4. STRATEGY
5. ML
6. FUNDAMENTAL
7. SENTIMENT
8. NEWS_MACRO
9. CE case
10. PE case
11. CONTRARIAN
12. RISK
13. QA
14. FINAL decision

## Structured-agent principle

Agents do not receive raw database dumps.

They receive structured:
- market state;
- deterministic features;
- market structure;
- option-chain analysis;
- strategy candidates;
- ML predictions;
- fundamental summary;
- sentiment summary;
- news/macro context.

The quantitative layer remains the source of truth for critical numbers.

## CE vs PE debate

The debate explicitly produces:
- CE case;
- PE case;
- contrarian challenge;
- CE score;
- PE score;
- conflicts;
- final debate winner.

The winner can be:
- CE
- PE
- NO_TRADE

A small CE/PE difference should produce no trade rather than a forced direction.

## Risk veto

Risk can block the entire decision for:
- unavailable option data;
- stale data;
- poor R:R;
- no clear debate winner;
- other critical constraints.

## QA veto

QA checks whether required analytical state exists.

This is separate from Risk so data/architecture failures are not disguised as
market opinions.

## Fundamental/sentiment/news

These agents are currently structured ingestion consumers. They do not invent
data.

Their source adapters will be connected in later work.

## Final output

The agent layer can return:
- BUY_CE
- BUY_PE
- WAIT
- NO_TRADE

along with:
- confidence;
- rationale;
- blockers;
- invalidation;
- CE/PE debate;
- risk veto;
- QA state.

The layer still does not place orders.

## API

`POST /phase13/analyze`

## Phase gate

Before Phase 14:
- [ ] Connect real fundamental data.
- [ ] Connect real sentiment/news sources.
- [ ] Connect Phase 12 OOS ML predictions.
- [ ] Persist agent runs and explanations.
- [ ] Add LLM provider abstraction.
- [ ] Give LLMs structured inputs only.
- [ ] Add independent QA checks around model outputs.
- [ ] Add debate transcripts/audit records.
- [ ] Add agent performance attribution.
- [ ] Add confidence calibration.
