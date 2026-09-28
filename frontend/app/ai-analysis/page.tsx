"use client";

import { Shell } from "../../components/Shell";
import { useCallback, useEffect, useState } from "react";

function finite(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function text(value: unknown, fallback = "—"): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function tone(value: string) {
  const v = value.toUpperCase();
  if (["BUY", "CALL", "LONG", "BULLISH", "APPROVED", "ACTIVE"].includes(v)) return "good";
  if (["SELL", "PUT", "SHORT", "BEARISH", "BLOCKED", "NO_TRADE", "STOPPED"].includes(v)) return "bad";
  if (["WAIT", "PENDING", "NEUTRAL"].includes(v)) return "warn";
  return "neutral";
}

function SparkleIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3 13.8 8.2 19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/>
      <path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z" fill="currentColor"/>
    </svg>
  );
}

function BotIcon() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="5" y="7" width="14" height="12" rx="3" stroke="currentColor" strokeWidth="1.6"/>
      <path d="M12 4v3M8.5 12h.01M15.5 12h.01M9 16h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3 19 6v5c0 4.5-2.7 8-7 10-4.3-2-7-5.5-7-10V6l7-3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/>
      <path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export default function AIAnalysis() {
  const API =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API}/ui/ai-analysis`, {
        cache: "no-store",
      });

      const body = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : body?.reason || `API ${response.status}`,
        );
      }

      setData(body);
      setError("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "AI Analysis backend unavailable",
      );
    } finally {
      setLoading(false);
    }
  }, [API]);

  useEffect(() => {
    void refresh();

    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);

    return () => window.clearInterval(timer);
  }, [refresh]);

  const result = data ?? {};
  const signal = result?.signal ?? {};
  const risk = result?.risk ?? {};
  const debate = result?.debate ?? {};
  const finalDecision = result?.final_decision ?? {};

  const direction = text(
    finalDecision?.direction ??
      finalDecision?.action ??
      signal?.direction ??
      signal?.action,
  );

  const score = finite(
    signal?.score ??
      finalDecision?.score,
  );

  const riskAction = text(
    risk?.final_action ??
      risk?.decision,
    risk?.approved ? "APPROVED" : "BLOCKED",
  );

  const optionSide = text(
    finalDecision?.option_side ??
      finalDecision?.side ??
      signal?.option_side,
  );

  const strike = finite(
    finalDecision?.strike ??
      signal?.strike,
  );

  const expiry = text(
    finalDecision?.expiry ??
      signal?.expiry,
  );

  const ce = debate?.ce ?? debate?.call ?? {};
  const pe = debate?.pe ?? debate?.put ?? {};
  const fused =
    finalDecision?.direction ||
    finalDecision?.action ||
    finalDecision
      ? finalDecision
      : signal;

  const ceDirection = text(
    ce?.direction ?? ce?.action ?? ce?.bias,
  );

  const peDirection = text(
    pe?.direction ?? pe?.action ?? pe?.bias,
  );

  const fusedDirection = text(
    finalDecision?.direction ??
      finalDecision?.action ??
      finalDecision?.decision ??
      direction,
  );

  const ceScore = finite(
    ce?.score ?? ce?.confidence,
  );

  const peScore = finite(
    pe?.score ?? pe?.confidence,
  );

  const fusedScore = finite(
    finalDecision?.score ??
      finalDecision?.confidence ??
      score,
  );

  const hasDebate =
    Array.isArray(data?.agents)
      ? data.agents.length > 0 || Object.keys(debate || {}).length > 0
      : Object.keys(debate || {}).length > 0;

  const lastUpdate =
    data?.timestamp || null;
  return (
    <Shell>
      <div className="topbar">
        <div className="row" style={{ gap: 12 }}>
          <div className="ai-page-icon"><SparkleIcon /></div>
          <div>
            <div className="eyebrow">Research</div>
            <h1>AI Analysis</h1>
            <p className="small" style={{ marginTop: 5 }}>
              Multi-agent decision view from the live pipeline.
            </p>
          </div>
        </div>
        <div className="status">
          <span className="dot" />
          {loading
            ? "Refreshing"
            : error
              ? "Backend unavailable"
              : data?.live
                ? "Live pipeline data"
                :data?.available
                  ? "Latest available data"
                  : "Waiting for AI result"}
        </div>
      </div>

      {error ? <div className="error ai-message">{error}</div> : null}

      <section className="ai-summary card">
        <div className="ai-summary-title">
          <div>
            <div className="eyebrow">Fused decision</div>
            <h2 className="section-title" style={{ marginTop: 5, marginBottom: 5 }}>
              {fusedDirection}
            </h2>
            <div className="small">
              {strike === null ? "Strike —" : `Strike ${strike}`}
              {expiry === "—" ? "" : ` · Expiry ${expiry}`}
              {optionSide === "—" ? "" : ` · ${optionSide}`}
            </div>
          </div>
          <span className={`pill ${tone(riskAction)}`}>{riskAction.toUpperCase()}</span>
        </div>

        <div className="ai-summary-grid">
          <div>
            <span>Signal score</span>
            <strong>{score === null ? "—" : score.toFixed(2)}</strong>
          </div>
          <div>
            <span>Fused confidence</span>
            <strong>
              {!data?.live || !fused ? "—" : fusedScore === null ? "—" : fusedScore.toFixed(2)}
            </strong>
          </div>
          <div>
            <span>Risk decision</span>
            <strong>{riskAction}</strong>
          </div>
          <div>
            <span>Last update</span>
            <strong>{lastUpdate ? String(lastUpdate) : "—"}</strong>
          </div>
        </div>
      </section>

      <section className="ai-debate-grid">
        <article className="card ai-panel ce-panel">
          <div className="ai-panel-head">
            <div>
              <div className="eyebrow">Call thesis</div>
              <h3>CE Analysis</h3>
            </div>
            <div className="ai-panel-icon"><BotIcon /></div>
          </div>

          {hasDebate && ceDirection !== "—" ? (
            <>
              <span className={`pill ${tone(ceDirection)}`}>{ceDirection.toUpperCase()}</span>
              <div className="ai-big-number">
                {ceScore === null ? "—" : ceScore.toFixed(2)}
              </div>
              <div className="small">Agent score / confidence</div>
              <div className="ai-evidence">
                {text(ce?.reason ?? ce?.rationale ?? ce?.thesis, "No CE rationale returned.")}
              </div>
            </>
          ) : (
            <div className="ai-empty">
              <strong>CE analysis unavailable</strong>
              <span>The backend has not returned a separate call-agent payload.</span>
            </div>
          )}
        </article>

        <article className="card ai-panel pe-panel">
          <div className="ai-panel-head">
            <div>
              <div className="eyebrow">Put thesis</div>
              <h3>PE Analysis</h3>
            </div>
            <div className="ai-panel-icon"><BotIcon /></div>
          </div>

          {hasDebate && peDirection !== "—" ? (
            <>
              <span className={`pill ${tone(peDirection)}`}>{peDirection.toUpperCase()}</span>
              <div className="ai-big-number">
                {peScore === null ? "—" : peScore.toFixed(2)}
              </div>
              <div className="small">Agent score / confidence</div>
              <div className="ai-evidence">
                {text(pe?.reason ?? pe?.rationale ?? pe?.thesis, "No PE rationale returned.")}
              </div>
            </>
          ) : (
            <div className="ai-empty">
              <strong>PE analysis unavailable</strong>
              <span>The backend has not returned a separate put-agent payload.</span>
            </div>
          )}
        </article>
      </section>

      <section className="card ai-fusion">
        <div className="ai-fusion-head">
          <div>
            <div className="eyebrow">Decision synthesis</div>
            <h3>Fused reasoning</h3>
          </div>
          <div className="ai-panel-icon"><SparkleIcon /></div>
        </div>

        <div className="ai-fusion-grid">
          <div>
            <span>Direction</span>
            <strong>
              {!data?.live ? "NO LIVE DECISION" : fusedDirection}
            </strong>
          </div>
          <div>
            <span>Risk gate</span>
            <strong>{riskAction}</strong>
          </div>
          <div>
            <span>Option side</span>
            <strong>{optionSide}</strong>
          </div>
        </div>

        <div className="ai-reasoning">
          <div className="ai-reasoning-icon"><ShieldIcon /></div>
          <div>
            <strong>Risk-aware synthesis</strong>
            <p>
              {text(
                fused?.reason ?? fused?.rationale ?? debate?.reasoning ?? debate?.summary,
                "No fused rationale was returned by the backend."
              )}
            </p>
          </div>
        </div>
      </section>

      <div className="note">
        This view does not invent agent opinions, confidence, or explanations. A panel remains unavailable until
        the corresponding backend payload exists.
      </div>
    </Shell>
  );
}
