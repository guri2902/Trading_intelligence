"use client";

import { Shell } from "../../components/Shell";
import { useCallback, useEffect, useState } from "react";

type Tone = "good" | "warn" | "bad" | "neutral";

function finite(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function text(value: unknown, fallback = "—"): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function Icon({ kind }: { kind: "technical" | "structure" | "options" | "sentiment" | "fundamentals" | "ml" }) {
  const common = {
    width: 22,
    height: 22,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  if (kind === "technical") {
    return (
      <svg {...common}>
        <path d="M4 17 9 12l3 3 8-9" />
        <path d="M17 6h3v3" />
        <path d="M5 20h14" />
      </svg>
    );
  }

  if (kind === "structure") {
    return (
      <svg {...common}>
        <path d="M5 18V9" />
        <path d="M12 18V5" />
        <path d="M19 18v-7" />
        <path d="M3 18h18" />
        <path d="m4 9 4-3 4 2 4-4 4 2" />
      </svg>
    );
  }

  if (kind === "options") {
    return (
      <svg {...common}>
        <path d="M4 7h16M4 12h16M4 17h16" />
        <circle cx="9" cy="7" r="1.5" />
        <circle cx="15" cy="12" r="1.5" />
        <circle cx="11" cy="17" r="1.5" />
      </svg>
    );
  }

  if (kind === "sentiment") {
    return (
      <svg {...common}>
        <path d="M12 20a8 8 0 1 0-8-8c0 2.2.9 4.2 2.4 5.7L5 20l3.8-1.2A8 8 0 0 0 12 20Z" />
        <path d="M9 10h.01M15 10h.01" />
        <path d="M9 14c1.6 1.2 4.4 1.2 6 0" />
      </svg>
    );
  }

  if (kind === "fundamentals") {
    return (
      <svg {...common}>
        <path d="M4 19V5" />
        <path d="M4 19h16" />
        <path d="M7 16v-4" />
        <path d="M11 16V8" />
        <path d="M15 16v-6" />
        <path d="M19 16v-9" />
      </svg>
    );
  }

  return (
    <svg {...common}>
      <path d="M12 3 14.2 8.1 20 9l-4.1 3.9 1 5.7L12 16l-4.9 2.6 1-5.7L4 9l5.8-.9L12 3Z" />
    </svg>
  );
}

function statusTone(status: string): Tone {
  const s = status.toUpperCase();
  if (["CONNECTED", "READY", "AVAILABLE", "PASS"].includes(s)) return "good";
  if (["BLOCKED", "ERROR", "NO_TRADE", "UNAVAILABLE"].includes(s)) return "bad";
  if (["WAIT", "PENDING", "NOT CONNECTED"].includes(s)) return "warn";
  return "neutral";
}

function Card({
  kind,
  title,
  eyebrow,
  status,
  children,
}: {
  kind: "technical" | "structure" | "options" | "sentiment" | "fundamentals" | "ml";
  title: string;
  eyebrow: string;
  status: string;
  children: React.ReactNode;
}) {
  return (
    <article className="card analysis-card">
      <div className="analysis-card-top">
        <div className="analysis-icon">
          <Icon kind={kind} />
        </div>
        <span className={`pill ${statusTone(status)}`}>{status}</span>
      </div>

      <div className="eyebrow" style={{ marginTop: 14 }}>{eyebrow}</div>
      <h3 className="analysis-card-title">{title}</h3>
      <div className="analysis-card-body">{children}</div>
    </article>
  );
}

export default function Analysis() {
  const API =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API}/ui/analysis`, {
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
          : "Analysis backend unavailable",
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

  const features = result?.technical ?? {};
  const structure = result?.structure ?? {};
  const options = result?.options ?? {};
  const signal = result?.signal ?? {};

  const rsi = finite(features?.rsi14 ?? features?.rsi);
  const ema9 = finite(features?.ema9);
  const ema20 = finite(features?.ema20);
  const ema50 = finite(features?.ema50);
  const atr = finite(features?.atr14 ?? features?.atr);
  const volumeRatio = finite(features?.relative_volume ?? features?.volume_ratio);

  const trend = text(structure?.trend);
  const regime = text(structure?.regime);
  const bos = text(structure?.bos ?? structure?.break_of_structure);
  const choch = text(structure?.choch);
  const support = finite(structure?.support);
  const resistance = finite(structure?.resistance);

  const atm = finite(options?.atm_strike);
  const expiry = text(options?.expiry);
  const optionBias = text(options?.bias ?? options?.side ?? options?.selected_side);
  const debate = options?.debate;

  const mlAvailable = Boolean(result?.signal || result?.ml || result?.prediction);
  const mlDirection = text(signal?.direction ?? signal?.action ?? result?.ml?.direction);
  const mlScore = finite(signal?.score ?? result?.ml?.score);

  return (
    <Shell>
      <div className="topbar">
        <div>
          <div className="eyebrow">Research</div>
          <h1>Market Analysis</h1>
          <p className="small" style={{ marginTop: 6 }}>
            Six research lenses. Live values only; unavailable providers stay explicitly unavailable.
          </p>
        </div>

        <div className="status">
          <span className="dot" />
          {loading
            ? "Refreshing"
            : error
              ? "Backend unavailable"
              : data?.live
                ? "Live pipeline data"
                : data?.available
                  ? "Latest available data"
                  : "Market closed"}
        </div>
      </div>

      {error ? <div className="error analysis-message">{error}</div> : null}

      <section className="grid cols3 analysis-grid">
        <Card
          kind="technical"
          eyebrow="Technical"
          title="Technical / Indicators"
          status={rsi !== null || ema20 !== null ? "AVAILABLE" : "WAIT"}
        >
          <div className="analysis-stat-grid">
            <div><span>RSI</span><strong>{rsi === null ? "—" : rsi.toFixed(2)}</strong></div>
            <div><span>ATR</span><strong>{atr === null ? "—" : atr.toFixed(2)}</strong></div>
            <div><span>EMA 9</span><strong>{ema9 === null ? "—" : ema9.toFixed(2)}</strong></div>
            <div><span>EMA 20</span><strong>{ema20 === null ? "—" : ema20.toFixed(2)}</strong></div>
          </div>
          <div className="analysis-meta">
            EMA 50: {ema50 === null ? "—" : ema50.toFixed(2)} · Relative volume: {volumeRatio === null ? "—" : volumeRatio.toFixed(2)}
          </div>
        </Card>

        <Card
          kind="structure"
          eyebrow="Structure"
          title="Market Structure"
          status={trend !== "—" || regime !== "—" ? "AVAILABLE" : "WAIT"}
        >
          <div className="analysis-highlight">{trend}</div>
          <div className="analysis-meta">Regime: {regime}</div>
          <div className="analysis-meta">BOS: {bos} · CHOCH: {choch}</div>
          <div className="analysis-levels">
            <span>Support <strong>{support === null ? "—" : support.toFixed(2)}</strong></span>
            <span>Resistance <strong>{resistance === null ? "—" : resistance.toFixed(2)}</strong></span>
          </div>
        </Card>

        <Card
          kind="options"
          eyebrow="Derivatives"
          title="Options Positioning"
          status={atm !== null || expiry !== "—" ? "AVAILABLE" : "WAIT"}
        >
          <div className="analysis-highlight">
            {atm === null ? "ATM —" : `ATM ${atm}`}
          </div>
          <div className="analysis-meta">Expiry: {expiry}</div>
          <div className="analysis-meta">Bias / side: {optionBias}</div>
          <div className="analysis-meta">
            Debate: {debate ? "Available" : "Waiting"}
          </div>
        </Card>

        <Card
          kind="sentiment"
          eyebrow="External data"
          title="Sentiment + News"
          status="NOT CONNECTED"
        >
          <div className="analysis-empty">
            <strong>Live provider not connected</strong>
            <span>Sentiment and news evidence are intentionally not inferred from the current pipeline.</span>
          </div>
        </Card>

        <Card
          kind="fundamentals"
          eyebrow="External data"
          title="Fundamentals"
          status="NOT CONNECTED"
        >
          <div className="analysis-empty">
            <strong>Live provider not connected</strong>
            <span>Fundamental data is unavailable in the current backend contract.</span>
          </div>
        </Card>

        <Card
          kind="ml"
          eyebrow="Model evidence"
          title="ML / Signal Evidence"
          status={mlAvailable ? "READY" : "WAIT"}
        >
          {mlAvailable ? (
            <>
              <div className="analysis-highlight">{mlDirection}</div>
              <div className="analysis-meta">
                Signal score: {mlScore === null ? "—" : mlScore.toFixed(2)}
              </div>
              <div className="analysis-meta">
                Source: live pipeline result
              </div>
            </>
          ) : (
            <div className="analysis-empty">
              <strong>Waiting for model payload</strong>
              <span>No model score or signal object has been returned yet.</span>
            </div>
          )}
        </Card>
      </section>

      <section className="card analysis-footnote">
        <div className="eyebrow">Research integrity</div>
        <div className="section-title" style={{ marginTop: 5, marginBottom: 5 }}>
          Unavailable data stays unavailable
        </div>
        <div className="small">
          This page does not estimate news sentiment, fundamentals, option Greeks, or ML confidence when those
          fields are absent from the backend response.
        </div>
      </section>
    </Shell>
  );
}
