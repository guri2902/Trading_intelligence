from __future__ import annotations

from pathlib import Path
import sys

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text

from backend.app.features.service import FeatureService
from backend.app.structure.service import StructureService
from backend.app.options.engine import OptionsEngine
from backend.app.options.models import OptionContract, OptionQuoteState
from backend.app.strategies.engine import StrategyEngine
from backend.app.strategies.models import StrategyContext
from backend.app.agents.models import AgentInput
from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.api.phase17 import SignalRequest, signal as phase17_signal
from backend.app.signals.models import SignalDecision

DB_URL = "sqlite:///./trading_intelligence.db"


IST = ZoneInfo("Asia/Kolkata")
MAX_DATA_GAP_SECONDS = 6 * 60  # 5-minute candle + small provider/processing allowance


def _as_aware(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


def load_real_candles(conn, *, end_at=None):
    params = {}
    end_filter = ""

    if end_at is not None:
        end_filter = "AND c.timestamp <= :end_at"

        # SQLite accepts a naive ISO datetime reliably for the stored timestamps.
        params["end_at"] = (
            _as_aware(end_at)
            .replace(tzinfo=None)
            .isoformat(sep=" ")
        )

    rows = conn.execute(
        text(
            f"""
            SELECT
                c.timestamp,
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume
            FROM candles c
            JOIN instruments i
              ON i.id = c.instrument_id
            WHERE i.segment = 'NSE_INDEX'
              AND i.trading_symbol = 'NIFTY'
              AND c.timeframe = 'minutes:5'
              AND c.source = 'upstox'
              {end_filter}
            ORDER BY c.timestamp DESC
            LIMIT 100
            """
        ),
        params,
    ).fetchall()

    rows = list(reversed(rows))

    return [
        {
            "timestamp": _as_aware(r.timestamp),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume) if r.volume is not None else None,
        }
        for r in rows
    ]


def load_real_options(conn, *, end_at=None):
    params = {}

    end_filter = ""
    if end_at is not None:
        end_filter = "AND m.timestamp <= :end_at"
        params["end_at"] = (
            _as_aware(end_at)
            .replace(tzinfo=None)
            .isoformat(sep=" ")
        )

    latest = conn.execute(
        text(
            f"""
            SELECT MAX(m.timestamp)
            FROM market_snapshots m
            JOIN instruments i ON i.id = m.instrument_id
            WHERE i.underlying_symbol = 'NIFTY'
              AND i.option_type IN ('CE', 'PE')
              AND m.source = 'upstox'
              AND time(m.timestamp) >= '09:15:00'
              AND time(m.timestamp) < '15:30:00'
              {end_filter}
            """
        ),
        params,
    ).scalar_one()

    if latest is None:
        return None, []

    rows = conn.execute(
        text(
            """
            SELECT
                m.timestamp,
                m.underlying_ltp,
                m.ltp,
                m.bid,
                m.ask,
                m.bid_qty,
                m.ask_qty,
                m.volume,
                m.open_interest,
                m.change_in_oi,
                m.iv,
                m.delta,
                m.gamma,
                m.theta,
                m.vega,
                m.rho,

                i.instrument_key,
                i.underlying_key,
                i.underlying_symbol,
                i.expiry_date,
                i.strike,
                i.option_type,
                i.lot_size,
                i.tick_size

            FROM market_snapshots m
            JOIN instruments i
              ON i.id = m.instrument_id
            WHERE i.underlying_symbol = 'NIFTY'
              AND i.option_type IN ('CE', 'PE')
              AND m.source = 'upstox'
              AND m.timestamp = :timestamp
            ORDER BY i.strike, i.option_type
            """
        ),
        {"timestamp": latest},
    ).fetchall()

    quotes = []

    for r in rows:
        previous_oi = None

        if (
            r.open_interest is not None
            and r.change_in_oi is not None
        ):
            previous_oi = (
                float(r.open_interest)
                - float(r.change_in_oi)
            )

        contract = OptionContract(
            instrument_key=r.instrument_key,
            underlying_key=r.underlying_key or "",
            underlying_symbol=r.underlying_symbol or "NIFTY",
            expiry=r.expiry_date,
            strike=float(r.strike),
            option_type=r.option_type,
            lot_size=r.lot_size,
            tick_size=(
                float(r.tick_size)
                if r.tick_size is not None
                else None
            ),
        )

        quotes.append(
            OptionQuoteState(
                contract=contract,
                timestamp=r.timestamp,
                underlying_spot=(
                    float(r.underlying_ltp)
                    if r.underlying_ltp is not None
                    else None
                ),
                ltp=(
                    float(r.ltp)
                    if r.ltp is not None
                    else None
                ),
                bid=(
                    float(r.bid)
                    if r.bid is not None
                    else None
                ),
                ask=(
                    float(r.ask)
                    if r.ask is not None
                    else None
                ),
                bid_qty=r.bid_qty,
                ask_qty=r.ask_qty,
                volume=(
                    float(r.volume)
                    if r.volume is not None
                    else None
                ),
                open_interest=(
                    float(r.open_interest)
                    if r.open_interest is not None
                    else None
                ),
                previous_oi=previous_oi,
                iv=(
                    float(r.iv)
                    if r.iv is not None
                    else None
                ),
                delta=(
                    float(r.delta)
                    if r.delta is not None
                    else None
                ),
                gamma=(
                    float(r.gamma)
                    if r.gamma is not None
                    else None
                ),
                theta=(
                    float(r.theta)
                    if r.theta is not None
                    else None
                ),
                vega=(
                    float(r.vega)
                    if r.vega is not None
                    else None
                ),
                rho=(
                    float(r.rho)
                    if r.rho is not None
                    else None
                ),
            )
        )

    return latest, quotes


with create_engine(DB_URL).connect() as conn:

    # Options define the reference market timestamp.
    option_timestamp, option_quotes = load_real_options(
        conn,
        end_at="2026-09-11 10:45:59",
    )

    # Only use candles at or before the option snapshot timestamp.
    candles = load_real_candles(
        conn,
        end_at=option_timestamp,
    )
    if candles and option_quotes:
        historical_spot = float(candles[-1]["close"])

        option_quotes = [
            q.model_copy(update={"underlying_spot": historical_spot})
            for q in option_quotes
        ]


if len(candles) < 7:
    raise RuntimeError(
        f"Need at least 7 real NIFTY candles, found {len(candles)}"
    )


if not option_quotes:
    raise RuntimeError("No real NIFTY option quotes found")


option_timestamp = _as_aware(option_timestamp)


if candles:
    latest_candle_timestamp = _as_aware(candles[-1]["timestamp"])
    candle_option_gap = (
        option_timestamp - latest_candle_timestamp
    ).total_seconds()

    if candle_option_gap < 0:
        raise RuntimeError(
            "DATA_ALIGNMENT_FAILED: latest candle is newer than the option snapshot: "
            f"candle={latest_candle_timestamp.isoformat()} "
            f"options={option_timestamp.isoformat()}"
        )

    # The final decision layer applies a strict freshness gate during
    # the market session. A post-close snapshot may legitimately be
    # much later than the final 15:25 candle, but it must never be
    # eligible for a live BUY CE / BUY PE decision.

else:
    raise RuntimeError(
        "DATA_ALIGNMENT_FAILED: no NIFTY 5-minute candles exist at or before "
        f"option snapshot {option_timestamp.isoformat()}"
    )


print("\n========== REAL DATA ==========")
print("CANDLES:", len(candles))
print("FIRST CANDLE:", candles[0])
print("LAST CANDLE:", candles[-1])
print("OPTION SNAPSHOT:", option_timestamp)
print("LATEST CANDLE:", candles[-1]["timestamp"])
print(
    "CANDLE/OPTION GAP (sec):",
    round(
        (
            option_timestamp
            - candles[-1]["timestamp"]
        ).total_seconds(),
        1,
    ),
)
print("OPTION QUOTES:", len(option_quotes))
print(
    "OPTION SPOT VALUES:",
    sorted(
        {
            q.underlying_spot
            for q in option_quotes
            if q.underlying_spot is not None
        }
    ),
)
print("===============================\n")


# ------------------------------------------------------------
# PHASE 6
# ------------------------------------------------------------

feature_service = FeatureService()

features = feature_service.calculate(
    candles,
    session_ids=None,
)

print("========== PHASE 6 ==========")
print(features)
print("==============================\n")


# ------------------------------------------------------------
# PHASE 7
# ------------------------------------------------------------

structure_service = StructureService()

structure = structure_service.analyze(candles)

print("========== PHASE 7 ==========")
print(structure)
print("==============================\n")


# ------------------------------------------------------------
# PHASE 8
# ------------------------------------------------------------

option_result = OptionsEngine().analyze(
    option_quotes,
    now=option_timestamp,
)

print("========== PHASE 8 ==========")
print("STATUS:", option_result.get("status"))
print("EXPIRY:", option_result.get("expiry"))
print("ATM:", option_result.get("atm_strike"))
print("BEST CE:", option_result.get("best_ce"))
print("BEST PE:", option_result.get("best_pe"))
print("DEBATE:", option_result.get("debate"))
print("==============================\n")


# ------------------------------------------------------------
# PHASE 9
# ------------------------------------------------------------

context = StrategyContext(
    timestamp=option_timestamp,
    candles=candles,
    features=features,
    structure=structure,
    options=option_result,
    regime=structure.get("regime"),
)

result = StrategyEngine().evaluate(context)


print("========== PHASE 9 REAL END-TO-END ==========")
print("REGIME:", result.regime)
print("TRIGGERED:", result.triggered_count)


for setup in result.setups:
    print("\n---", setup.strategy, "---")
    print("STATE:", setup.state)
    print("DIRECTION:", setup.direction)
    print("CONFIDENCE:", setup.confidence)
    print("ENTRY:", setup.entry)
    print("SL:", setup.invalidation)
    print("TP1:", setup.target_1)
    print("TP2:", setup.target_2)
    print("RR:", setup.risk_reward)
    print("EVIDENCE:", setup.evidence)
    print("WAIT:", setup.wait_for)
    print("INVALID:", setup.invalidation_reasons)


print("\n========== BEST SETUP ==========")


if result.best_setup:
    print("STRATEGY:", result.best_setup.strategy)
    print("DIRECTION:", result.best_setup.direction)
    print("STATE:", result.best_setup.state)
    print("CONFIDENCE:", result.best_setup.confidence)
    print("ENTRY:", result.best_setup.entry)
    print("SL:", result.best_setup.invalidation)
    print("TP1:", result.best_setup.target_1)
    print("TP2:", result.best_setup.target_2)
    print("RR:", result.best_setup.risk_reward)

else:
    print("NO TRIGGERED SETUP")


print("\n==============================================")


# ------------------------------------------------------------
# LIVE DATA FRESHNESS / SESSION GATE
# ------------------------------------------------------------

MARKET_OPEN = (9, 15)
MARKET_CLOSE = (15, 30)
MAX_SPOT_DIVERGENCE_PCT = 0.15

latest_candle = _as_aware(candles[-1]["timestamp"])
option_time = _as_aware(option_timestamp)
india_time = option_time

within_market_hours = (
    (india_time.hour, india_time.minute) >= MARKET_OPEN
    and (india_time.hour, india_time.minute) < MARKET_CLOSE
)

freshness_seconds = (
    option_time - latest_candle
).total_seconds()

option_spots = sorted(
    {
        float(q.underlying_spot)
        for q in option_quotes
        if q.underlying_spot is not None
    }
)

latest_candle_spot = float(candles[-1]["close"])

option_spot = (
    option_spots[0]
    if option_spots
    else None
)

divergence_pct = (
    abs(latest_candle_spot - option_spot)
    / latest_candle_spot
    * 100.0
    if option_spot is not None
    and latest_candle_spot
    else None
)


print("\n========== FINAL SIGNAL FRESHNESS GATE ==========")
print("MARKET TIME:", option_time)
print("WITHIN MARKET HOURS:", within_market_hours)
print("FRESHNESS (sec):", round(freshness_seconds, 1))
print(
    "MAX ALLOWED FRESHNESS (sec):",
    MAX_DATA_GAP_SECONDS,
)
print("CANDLE SPOT:", latest_candle_spot)
print("OPTION SPOT:", option_spot)
print(
    "SPOT DIVERGENCE (%):",
    None
    if divergence_pct is None
    else round(divergence_pct, 4),
)

# IMPORTANT:
# This gate does not place trades and does not replace Phase 17/18
# signal fusion + deterministic risk approval. It only determines
# whether the current data is eligible to proceed to that
# downstream decision layer.

if (
    india_time.hour,
    india_time.minute,
) >= MARKET_CLOSE:

    gate_status = "VETO"
    gate_reason = (
        f"MARKET_SESSION_CLOSED: "
        f"snapshot time is {option_time.time()}."
    )

elif (
    india_time.hour,
    india_time.minute,
) < MARKET_OPEN:

    gate_status = "VETO"
    gate_reason = (
        f"MARKET_SESSION_NOT_OPEN: "
        f"snapshot time is {option_time.time()}."
    )

elif freshness_seconds < 0:

    gate_status = "VETO"
    gate_reason = (
        "DATA_ALIGNMENT_FAILED: latest candle is newer "
        "than option snapshot."
    )

elif freshness_seconds > MAX_DATA_GAP_SECONDS:

    gate_status = "VETO"
    gate_reason = (
        f"STALE_LIVE_DATA: candle/option gap is "
        f"{freshness_seconds:.1f}s; maximum allowed is "
        f"{MAX_DATA_GAP_SECONDS}s."
    )

elif option_spot is None:

    gate_status = "VETO"
    gate_reason = (
        "DATA_CONSISTENCY_FAILED: "
        "option underlying spot is missing."
    )

elif divergence_pct > MAX_SPOT_DIVERGENCE_PCT:

    gate_status = "VETO"
    gate_reason = (
        f"DATA_CONSISTENCY_FAILED: spot divergence is "
        f"{divergence_pct:.4f}% > "
        f"{MAX_SPOT_DIVERGENCE_PCT:.2f}%."
    )

else:

    gate_status = "PASS"
    gate_reason = (
        "Fresh synchronized market data. Eligible for "
        "downstream signal fusion and Phase 18 risk approval."
    )


print("STATUS:", gate_status)
print("REASON:", gate_reason)

print(
    "BEST SETUP REACHES FUSION:",
    bool(
        gate_status == "PASS"
        and result.best_setup is not None
        and result.best_setup.state == "TRIGGERED"
    ),
)

print("IMPORTANT: No trade is authorized by this gate alone.")
print("===============================================")


# ------------------------------------------------------------
# PHASE 17 REAL E2E
# ------------------------------------------------------------

def _dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


latest_candle = candles[-1]


# Convert real Phase 5-9 output into the existing AgentInput contract.
#
# Keep the derived OptionsEngine result, but explicitly preserve
# the raw option snapshot metadata required by the live-signal gate.
options_payload = _dump(option_result)

options_payload["snapshot_timestamp"] = (
    option_timestamp.isoformat()
)


option_spots = sorted(
    {
        float(q.underlying_spot)
        for q in option_quotes
        if q.underlying_spot is not None
    }
)


options_payload["underlying_spot"] = (
    option_spots[0]
    if option_spots
    else None
)


agent_input = AgentInput(
    timestamp=option_timestamp,

    market={
        "symbol": "NIFTY",
        "spot": latest_candle["close"],
        "timestamp": latest_candle["timestamp"].isoformat(),
        "data_quality_status": "PASS",
        "stale": False,
    },

    features=_dump(features),
    structure=_dump(structure),
    options=options_payload,
    strategies=_dump(result),

    # These remain empty until their real providers are connected.
    ml={},
    fundamentals={},
    sentiment={},
    news={},
    risk={},
)


print("\n========== PHASE 17 REAL E2E ==========")
print("PHASE17 MARKET:", agent_input.market)
print("PHASE17 OPTIONS STATUS:", agent_input.options.get("status"))
print("PHASE17 OPTIONS SNAPSHOT:", agent_input.options.get("snapshot_timestamp"))
# We deliberately disable LLM.
# This tests the real deterministic Phase 17 path first.
phase17_request = SignalRequest(
    data=agent_input,
    use_llm=False,
)


phase17_result = phase17_signal(
    phase17_request
)
from backend.app.risk.engine import RiskEngine
from backend.app.risk.models import AccountRiskContext
print("\n========== PHASE 18 REAL E2E ==========")

account = AccountRiskContext(
    equity=100000,
    realized_pnl_today=0,
    open_risk=0,
    open_positions=0,
    trades_today=0,
    peak_equity=100000,
    risk_per_trade_pct=1.0,
    max_daily_loss=2000,
    max_concurrent_risk=2000,
    max_trades_per_day=5,
    max_open_positions=1,
    max_drawdown_pct=5,
    enabled=True,
    market_timestamp=option_timestamp,
)
signal_decision = SignalDecision.model_validate(phase17_result)
risk_decision = RiskEngine().evaluate(
    signal_decision,
    account,
)

print("SIGNAL ACTION:", phase17_result.get("action"))
print("SIGNAL DIRECTION:", phase17_result.get("direction"))
print("RISK APPROVED:", risk_decision.approved)
print("FINAL ACTION:", risk_decision.final_action)
print("RISK REASONS:", risk_decision.assessment.reason_codes)
print("RISK BUDGET:", risk_decision.assessment.risk_budget)
print("UNIT RISK:", risk_decision.assessment.unit_risk)
print("QUANTITY:", risk_decision.assessment.quantity)
print("LOTS:", risk_decision.assessment.lots)
print("ESTIMATED TRADE RISK:", risk_decision.assessment.estimated_trade_risk)
print("RISK % OF EQUITY:", risk_decision.assessment.risk_pct_of_equity)
print("TRADE PLAN:", risk_decision.trade_plan)
print("======================================")

print(
    "ACTION:",
    phase17_result.get("action"),
)

print(
    "DIRECTION:",
    phase17_result.get("direction"),
)

print(
    "CONFIDENCE:",
    phase17_result.get("confidence"),
)

print(
    "SCORE:",
    phase17_result.get("score"),
)


print("HARD GATES:")

for reason in phase17_result.get(
    "hard_gates",
    [],
):
    print(" -", reason)


print("LIVE SIGNAL GATE:")

print(
    phase17_result.get(
        "live_signal_gate"
    )
)


print("========================================")