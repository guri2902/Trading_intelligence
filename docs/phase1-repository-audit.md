# Indian Options Trading Intelligence Platform — Phase 1

## Phase 1 goal
Repository/provider audit and architecture decisions before implementing market-data ingestion.

## Decisions

| Component | Decision | Role |
|---|---|---|
| OptionVault | USE SELECTIVELY | Historical NSE cash/index/futures/options research and backtesting data |
| NautilusTrader | USE SELECTIVELY | Event-driven research/backtest/execution concepts; do not make it the whole application runtime initially |
| TauricResearch/TradingAgents | ADAPT | Analyst/debate role architecture: technical, fundamentals, sentiment, researchers, trader, risk |
| OpenBB | USE AS DATA/RESEARCH ABSTRACTION | Analyst/AI data access layer where its providers fit; do not make it the authoritative NSE options source |
| TradingView MCP | OPTIONAL ADAPTER | Supplemental chart/context/technical tooling; never the authoritative market-data source |
| Paperclip | NOT CORE | Agent organization/governance may be useful later, but it is not an agent framework; our signal pipeline needs deterministic orchestration |
| Ruflo | NOT CORE | Powerful general swarm/self-learning orchestration, but adds substantial complexity and overlaps with the specialized trading-agent layer |
| Vibe-Trading | RESEARCH ONLY | Useful ideas for self-improvement, MCP, options analytics and research memory; do not merge wholesale |
| Freqtrade/Hummingbot | NOT CORE | Wrong architectural center for NSE index/options intelligence |
| Qanat | HOLD | Verify repository relevance/licensing/integration value before any use |

## Critical architecture rule

Deterministic quantitative calculations are authoritative. Agents interpret, challenge and compare those calculations. Agents must not independently invent market state.

## Signal pipeline

REAL DATA
→ VALIDATION
→ NORMALIZATION
→ FEATURES
→ MARKET STRUCTURE
→ OPTIONS ENGINE
→ STRATEGIES
→ ML EVIDENCE
→ MULTI-AGENT DEBATE
→ RISK VETO
→ TRADE RANKING
→ BUY CE / BUY PE / WAIT / NO TRADE

## Data-source hierarchy

1. Upstox: broker-connected live/historical provider once credentials are supplied.
2. NSE: official option-chain source where legitimately accessible.
3. OptionVault / supplied datasets: historical research/backtesting.
4. OpenBB: normalized research/data abstraction for supported providers.
5. TradingView MCP: optional supplemental chart/context adapter.

No source is allowed to silently substitute for missing authoritative option-chain data.

## TradingView MCP decision

Use it only behind a `ChartContextProvider` interface. It can add chart snapshots, symbol discovery and technical context, but it should not become the pricing source of truth. The discovered open-source MCP is independent of TradingView, so licensing/data-entitlement checks are required before production use.

## Agent architecture

The initial specialist set is:

- Data Agent
- Technical Agent
- Options Agent
- Strategy Agent
- ML Agent
- Fundamental Agent
- Sentiment Agent
- News/Macro Agent
- CE Analyst
- PE Analyst
- Contrarian Agent
- Risk Agent
- Final Trader Agent
- QA/Provenance Agent

Agents consume structured state from the same market-state object.

## Self-improvement design

Self-improvement will NOT mean allowing an LLM to rewrite production trading logic automatically.

Instead:

1. Store every signal, evidence item, decision, risk veto and outcome.
2. Measure signal quality by strategy, regime, timeframe and option-selection policy.
3. Run walk-forward/OOS evaluation.
4. Generate candidate parameter/model changes.
5. Require validation gates before promotion.
6. Keep immutable production versions and an experiment registry.
7. Promote only candidates that beat the relevant baseline after costs and remain robust across regimes.

## Phase order

1. Repository audit — this phase
2. Data providers
3. Data validation
4. Database/storage
5. Feature engine
6. Market structure
7. Options engine
8. Strategy engine
9. Backtesting
10. Optuna optimization
11. ML validation
12. Multi-agent layer
13. Risk engine
14. Trade ranking
15. Paper trading
16. Backend/API
17. Frontend
18. Integration
19. Automated testing
20. Production hardening

The frontend will visualize a working system rather than fake market values.
