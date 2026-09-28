from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
MAX_FRESHNESS_SECONDS = int(os.getenv("LIVE_SIGNAL_MAX_GAP_SECONDS", "360"))
MAX_SPOT_DIVERGENCE_PCT = float(os.getenv("LIVE_SIGNAL_MAX_SPOT_DIVERGENCE_PCT", "0.15"))


@dataclass(frozen=True)
class LiveSignalGate:
    passed: bool
    reasons: list[str]
    candle_timestamp: datetime | None
    option_timestamp: datetime | None
    freshness_seconds: float | None
    candle_spot: float | None
    option_spot: float | None
    divergence_pct: float | None
    within_market_hours: bool | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "status": "PASS" if self.passed else "VETO",
            "reasons": self.reasons,
            "candle_timestamp": self.candle_timestamp.isoformat() if self.candle_timestamp else None,
            "option_timestamp": self.option_timestamp.isoformat() if self.option_timestamp else None,
            "freshness_seconds": self.freshness_seconds,
            "max_freshness_seconds": MAX_FRESHNESS_SECONDS,
            "candle_spot": self.candle_spot,
            "option_spot": self.option_spot,
            "spot_divergence_pct": self.divergence_pct,
            "max_spot_divergence_pct": MAX_SPOT_DIVERGENCE_PCT,
            "within_market_hours": self.within_market_hours,
        }


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def _first_float(*values: Any) -> float | None:
    for value in values:
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def evaluate_live_signal_gate(data: Any) -> LiveSignalGate:
    market = getattr(data, "market", {}) or {}
    options = getattr(data, "options", {}) or {}
    features = getattr(data, "features", {}) or {}

    candle_ts = _parse_ts(
        market.get("candle_timestamp")
        or market.get("latest_candle_timestamp")
        or features.get("timestamp")
        or getattr(data, "timestamp", None)
    )
    option_ts = _parse_ts(
        options.get("snapshot_timestamp")
        or options.get("option_timestamp")
        or options.get("timestamp")
        or options.get("latest_timestamp")
    )

    reasons: list[str] = []
    freshness: float | None = None
    if candle_ts is None:
        reasons.append("MISSING_CANDLE_TIMESTAMP")
    if option_ts is None:
        reasons.append("MISSING_OPTION_SNAPSHOT_TIMESTAMP")

    if candle_ts is not None and option_ts is not None:
        delta = (option_ts - candle_ts).total_seconds()
        freshness = round(delta, 3)
        if delta < 0:
            reasons.append("OPTION_SNAPSHOT_BEFORE_LATEST_CANDLE")
        elif delta > MAX_FRESHNESS_SECONDS:
            reasons.append(f"STALE_DATA:{delta:.1f}s>{MAX_FRESHNESS_SECONDS}s")

    session_ts = option_ts or candle_ts
    within_market_hours: bool | None = None
    if session_ts is not None:
        within_market_hours = MARKET_OPEN <= session_ts.time() <= MARKET_CLOSE
        if not within_market_hours:
            if session_ts.time() < MARKET_OPEN:
                reasons.append(f"MARKET_SESSION_NOT_STARTED:{session_ts.time().isoformat()}")
            else:
                reasons.append(f"MARKET_SESSION_CLOSED:{session_ts.time().isoformat()}")

    candle_spot = _first_float(
        market.get("candle_spot"),
        market.get("spot"),
        market.get("underlying_spot"),
        features.get("price"),
    )
    option_spot = _first_float(
        options.get("underlying_spot"),
        options.get("spot"),
    )
    if option_spot is None:
        candidates = options.get("candidates") or options.get("contracts") or []
        spots = []
        if isinstance(candidates, list):
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                value = _first_float(
                    item.get("underlying_spot"),
                    (item.get("quote") or {}).get("underlying_spot") if isinstance(item.get("quote"), dict) else None,
                )
                if value is not None:
                    spots.append(value)
        if spots:
            option_spot = spots[0]

    divergence_pct: float | None = None
    if candle_spot is None:
        reasons.append("MISSING_CANDLE_SPOT")
    if option_spot is None:
        reasons.append("MISSING_OPTION_SPOT")
    if candle_spot is not None and option_spot is not None and candle_spot > 0:
        divergence_pct = round(abs(candle_spot - option_spot) / candle_spot * 100.0, 6)
        if divergence_pct > MAX_SPOT_DIVERGENCE_PCT:
            reasons.append(
                f"SPOT_DIVERGENCE:{divergence_pct:.4f}%>{MAX_SPOT_DIVERGENCE_PCT:.4f}%"
            )

    if str(market.get("data_quality_status", "PASS")).upper() not in {"PASS", "OK"}:
        reasons.append("MARKET_DATA_QUALITY_NOT_PASS")
    if bool(market.get("stale")):
        reasons.append("STALE_MARKET_DATA")
    if str(options.get("status", "PASS")).upper() not in {"PASS", "OK"}:
        reasons.append("OPTION_DATA_NOT_AVAILABLE")

    # Preserve order while de-duplicating to make API/audit output stable.
    unique_reasons = list(dict.fromkeys(reasons))
    return LiveSignalGate(
        passed=not unique_reasons,
        reasons=unique_reasons,
        candle_timestamp=candle_ts,
        option_timestamp=option_ts,
        freshness_seconds=freshness,
        candle_spot=candle_spot,
        option_spot=option_spot,
        divergence_pct=divergence_pct,
        within_market_hours=within_market_hours,
    )
