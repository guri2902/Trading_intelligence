# Phase 6 — Deterministic Feature Engine

Adds a pure quantitative feature layer before market structure and strategy logic.

Features:
- EMA 9/20/50 and alignment
- RSI 14
- ATR 14
- session VWAP and VWAP distance
- relative volume 20
- 1/5/15-period returns
- momentum 10
- rolling volatility
- PDH/PDL/PDC
- day open/high/low
- candle range/body/wicks
- multi-timeframe alignment for 5m/15m/30m/1h

Design:
- deterministic only;
- no LLM/model calls;
- no trading decisions;
- no implicit timeframe resampling;
- backtesting caller must provide only information available at that historical point.

Endpoints:
- POST /phase6/features
- POST /phase6/features/multi-timeframe
