"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "../components/Shell";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type PipelineStatus = {
  running: boolean;
  cycle_count: number;
  last_error: string | null;
  interval_seconds: number | null;
  last_result?: {
    status?: string;
    timestamp?: string;
    candle_timestamp?: string;
    signal?: {
      action?: string;
      direction?: string;
      confidence?: number;
      score?: number;
      hard_gates?: string[];
      selected?: Record<string, unknown> | null;
      live_signal_gate?: {
        passed?: boolean;
        reasons?: string[];
      };
    };
    risk?: {
      approved?: boolean;
      final_action?: string;
      assessment?: {
        reason_codes?: string[];
        risk_budget?: number;
        quantity?: number;
        lots?: number;
        estimated_trade_risk?: number;
        risk_pct_of_equity?: number;
      };
    };
  };
};

type Tone = "neutral" | "good" | "bad" | "warning";

function toneForStatus(value: string): Tone {
  const normalized = value.toUpperCase();

  if (
    normalized.includes("APPROVED") ||
    normalized.includes("PASS") ||
    normalized.includes("LIVE") ||
    normalized.includes("RUNNING")
  ) {
    return "good";
  }

  if (
    normalized.includes("BLOCKED") ||
    normalized.includes("NO_TRADE") ||
    normalized.includes("STOPPED") ||
    normalized.includes("ERROR")
  ) {
    return "bad";
  }

  if (
    normalized.includes("WAIT") ||
    normalized.includes("UNKNOWN") ||
    normalized.includes("PENDING")
  ) {
    return "warning";
  }

  return "neutral";
}

function StatusPill({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: Tone;
}) {
  return (
    <span className={`pill ${tone}`}>
      {children}
    </span>
  );
}

function LockIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="5" y="10" width="14" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      <path d="M12 14v2" />
    </svg>
  );
}

export default function Home() {
  const [data, setData] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadStatus() {
    try {
      const response = await fetch(`${API_BASE}/pipeline/status`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }

      const payload = await response.json();
      setData(payload);
      setError("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Backend unavailable"
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();

    const timer = setInterval(loadStatus, 5000);
    return () => clearInterval(timer);
  }, []);

  const signal = data?.last_result?.signal;
  const risk = data?.last_result?.risk;

  const action = signal?.action || "WAIT";
  const finalAction = risk?.final_action || "NO_TRADE";

  const dataHealthy =
    Boolean(data?.running) &&
    data?.last_result?.status === "UPDATED" &&
    !data?.last_error;

  const marketGate = signal?.live_signal_gate?.passed
    ? "PASS"
    : "WAIT";

  const executionTone = "neutral";
  const dataTone = loading
    ? "neutral"
    : dataHealthy
      ? "good"
      : "warning";
  const riskTone = risk?.approved
    ? "good"
    : toneForStatus(finalAction);
  const pipelineTone = data?.running
    ? "good"
    : "bad";

  const pipelineStates = useMemo(
    () => [
      {
        code: "01",
        name: "Data validation",
        status: dataHealthy ? "PASS" : "WAIT",
        detail: dataHealthy
          ? "Latest pipeline result is current."
          : "Waiting for a fresh validated result.",
      },
      {
        code: "02",
        name: "Market structure",
        status: data?.last_result ? "READY" : "WAIT",
        detail: data?.last_result
          ? "Latest structure context is available."
          : "No current market-structure result.",
      },
      {
        code: "03",
        name: "Options engine",
        status: "READY",
        detail:
          "Historical/realtime options modules remain backend-controlled.",
      },
      {
        code: "04",
        name: "Strategy + ML",
        status: signal ? "READY" : "WAIT",
        detail: signal
          ? "Latest signal layer is available."
          : "No current strategy signal.",
      },
      {
        code: "05",
        name: "Agent debate",
        status: "READY",
        detail:
          "Agent orchestration is surfaced by the backend when available.",
      },
      {
        code: "06",
        name: "Risk + ranking",
        status: risk ? "READY" : "WAIT",
        detail: risk
          ? "Latest risk assessment is available."
          : "No current risk assessment.",
      },
    ],
    []
  );

  return (
    <Shell>
      <div className="topbar">
        <div>
          <div className="eyebrow">
            Market Command Center
          </div>
          <h1>Today’s decision layer</h1>
          <div className="small">
            Current system state from the live pipeline. No
            execution is submitted from this screen.
          </div>
        </div>

        <div
          className="status"
          title="Live order submission is intentionally disabled as a safety default."
        >
          <LockIcon />
          <span>Execution disabled by design</span>
        </div>
      </div>

      {/* Primary decision metrics */}
      <div className="grid cols4">
        <div className="card metric-primary">
          <h3>Top signal</h3>
          <div className="big">{action}</div>
          <StatusPill tone={toneForStatus(action)}>
            {action}
          </StatusPill>
          <div className="small" style={{ marginTop: 9 }}>
            Confidence:{" "}
            {signal?.confidence != null
              ? `${signal.confidence.toFixed(1)}%`
              : "—"}
          </div>
        </div>

        <div className="card">
          <h3>Data health</h3>
          <div className="big">
            {loading
              ? "..."
              : dataHealthy
                ? "LIVE"
                : "WAIT"}
          </div>
          <StatusPill tone={dataTone}>
            {loading
              ? "CHECKING"
              : dataHealthy
                ? "LIVE"
                : "WAIT"}
          </StatusPill>
          <div className="small" style={{ marginTop: 9 }}>
            {data?.cycle_count ?? 0} analysis cycle
            {data?.cycle_count === 1 ? "" : "s"} completed
          </div>
        </div>

        <div className="card metric-primary">
          <h3>Risk state</h3>
          <div className="big">
            {risk?.approved
              ? "APPROVED"
              : finalAction}
          </div>
          <StatusPill tone={riskTone}>
            {risk?.approved
              ? "APPROVED"
              : finalAction}
          </StatusPill>
          <div className="small" style={{ marginTop: 9 }}>
            {risk?.assessment?.estimated_trade_risk != null
              ? `Estimated trade risk ₹${Number(
                  risk.assessment.estimated_trade_risk
                ).toFixed(2)}`
              : "No approved trade"}
          </div>
        </div>

        <div className="card">
          <h3>Pipeline</h3>
          <div className="big">
            {data?.running
              ? "RUNNING"
              : "STOPPED"}
          </div>
          <StatusPill tone={pipelineTone}>
            {data?.running
              ? "RUNNING"
              : "STOPPED"}
          </StatusPill>
          <div className="small" style={{ marginTop: 9 }}>
            Refresh: {data?.interval_seconds ?? 30}s
          </div>
        </div>
      </div>

      {/* Live decision */}
      <div className="section">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className="section-title">
            Live decision
          </h2>
          <StatusPill tone={executionTone}>
            SAFETY DEFAULT
          </StatusPill>
        </div>

        <div className="grid cols3">
          <div className="card">
            <h3>Direction</h3>
            <div className="big">
              {signal?.direction || "NONE"}
            </div>
            <div className="small">
              Score:{" "}
              {signal?.score != null
                ? Number(signal.score).toFixed(2)
                : "—"}
            </div>
          </div>

          <div className="card">
            <h3>Risk decision</h3>
            <div className="big">
              {finalAction}
            </div>
            <div className="small">
              {risk?.assessment?.reason_codes?.length
                ? risk.assessment.reason_codes.join(", ")
                : "No current risk blockers reported"}
            </div>
          </div>

          <div className="card">
            <h3>Market gate</h3>
            <div className="big">
              {marketGate}
            </div>
            <div className="small">
              {signal?.live_signal_gate?.reasons?.length
                ? signal.live_signal_gate.reasons.join(", ")
                : "No gate failures reported"}
            </div>
          </div>
        </div>
      </div>

      {/* System pipeline */}
      <div className="section">
        <h2 className="section-title">
          Pipeline
        </h2>

        <div className="grid cols3">
          {pipelineStates.map((item) => (
            <div className="card" key={item.name}>
              <div
                className="row"
                style={{
                  justifyContent: "space-between",
                  marginBottom: 9,
                }}
              >
                <span className="small">
                  {item.code}
                </span>
                <StatusPill
                  tone={toneForStatus(item.status)}
                >
                  {item.status}
                </StatusPill>
              </div>
              <h3>{item.name}</h3>
              <div className="small">
                {item.detail}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Operational context */}
      <div className="grid cols2 section">
        <div className="card">
          <h3>Last update</h3>
          <div className="small">
            {data?.last_result?.timestamp ||
              "Waiting for the realtime pipeline."}
          </div>
          <div className="small" style={{ marginTop: 8 }}>
            Candle timestamp:{" "}
            {data?.last_result?.candle_timestamp ||
              "—"}
          </div>
        </div>

        <div className="card security-note">
          <div className="row">
            <LockIcon />
            <h3 style={{ margin: 0 }}>
              Execution safety
            </h3>
          </div>
          <div className="small" style={{ marginTop: 8 }}>
            Live order submission remains disabled by
            design. This page only reports the current
            decision state.
          </div>
        </div>
      </div>

      <div className="section note">
        {error
          ? `Backend connection error: ${error}`
          : data?.last_error
            ? `Pipeline error: ${data.last_error}`
            : data?.last_result?.timestamp
              ? `Last update: ${data.last_result.timestamp}`
              : "Waiting for the realtime pipeline to produce its first market result."}
      </div>
    </Shell>
  );
}
