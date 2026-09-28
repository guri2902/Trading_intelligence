"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "../../components/Shell";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type RiskConfig = {
  capital: number;
  per_trade_risk: number;
  daily_risk_budget: number;
  weekly_risk_budget: number;
  monthly_risk_budget: number;
  max_concurrent_risk: number;
  max_open_positions: number;
  max_trades_per_day: number;
  max_drawdown_pct: number;
  square_off_time: string;
  lot_sizes: Record<string, number>;
};

function finite(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function pct(value: unknown): string {
  const n = finite(value);
  return n === null ? "—" : `${n.toFixed(2)}%`;
}

function money(value: unknown): string {
  const n = finite(value);
  return n === null ? "—" : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function text(value: unknown, fallback = "—"): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function tone(value: string) {
  const s = value.toUpperCase();
  if (["SAFE", "PASS", "APPROVED", "ACTIVE", "NORMAL", "OK"].includes(s)) return "good";
  if (["BLOCKED", "STOPPED", "BREACH", "CRITICAL", "REJECTED", "DANGER"].includes(s)) return "bad";
  if (["WARN", "WARNING", "CAUTION", "THROTTLED", "PENDING"].includes(s)) return "warn";
  return "neutral";
}

function ShieldIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3 19 6v5c0 4.5-2.7 8-7 10-4.3-2-7-5.5-7-10V6l7-3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M9 12.2 11.2 14 15 10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="5" y="10" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 10V7a4 4 0 1 1 8 0v3" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function Metric({
  label,
  value,
  helper,
  status,
}: {
  label: string;
  value: string;
  helper?: string;
  status?: string;
}) {
  return (
    <div className="card risk-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {status ? <small className={`pill ${tone(status)}`}>{status}</small> : null}
      {helper ? <em>{helper}</em> : null}
    </div>
  );
}

export default function RiskPage() {
  const [data, setData] = useState<any>(null);
  const [config, setConfig] = useState<RiskConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingConfig, setSavingConfig] = useState(false);
  const [configSaved, setConfigSaved] = useState(false);
  const [error, setError] = useState("");

  async function loadConfig() {
    try {
      const response = await fetch(`${API}/ui/risk/config`, { cache: "no-store" });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : body?.reason || `Risk config API ${response.status}`,
        );
      }
      setConfig(body?.config ?? null);
    } catch (e: any) {
      setError(e?.message || "Unable to load risk configuration.");
    }
  }

  async function load() {
    try {
      setError("");

      const response = await fetch(`${API}/ui/risk`, {
        cache: "no-store",
      });

      const body = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : body?.reason || `Risk API ${response.status}`,
        );
      }

      setData(body);
    } catch (e: any) {
      setError(e?.message || "Unable to load risk state.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    void loadConfig();

    const timer = window.setInterval(() => {
      void load();
    }, 5000);

    return () => clearInterval(timer);
  }, []);

  const risk = data || {};
  const decision = text(risk?.decision ?? risk?.final_action ?? risk?.status);
  const state = text(risk?.state ?? risk?.risk_state ?? decision);
  const reason = text(risk?.reason ?? risk?.message ?? risk?.rationale);

  const dailyLoss = finite(risk?.daily_loss ?? risk?.today_loss ?? risk?.realized_loss);
  const dailyLossLimit = finite(risk?.daily_loss_limit ?? risk?.max_daily_loss);
  const dailyLossPct = dailyLossLimit && dailyLossLimit > 0 && dailyLoss !== null
    ? (Math.abs(dailyLoss) / dailyLossLimit) * 100
    : null;

  const drawdown = finite(risk?.drawdown_pct ?? risk?.current_drawdown_pct ?? risk?.max_drawdown_pct);
  const maxDrawdown = finite(risk?.max_drawdown_limit_pct ?? risk?.drawdown_limit_pct);
  const drawdownUsed = maxDrawdown && maxDrawdown > 0 && drawdown !== null
    ? (Math.abs(drawdown) / maxDrawdown) * 100
    : null;

  const riskPerTrade = finite(risk?.risk_per_trade ?? risk?.risk_per_trade_pct);
  const openPositions = finite(risk?.open_positions ?? risk?.position_count);
  const exposure = finite(risk?.exposure ?? risk?.gross_exposure);
  const tradingAllowed = Boolean(risk?.trading_allowed);

  const checks = useMemo(() => {
    const source = risk?.checks || risk?.gates || {};
    if (Array.isArray(source)) {
      return source.map((item: any, i: number) => ({
        id: i,
        name: text(item?.name ?? item?.check ?? `Check ${i + 1}`),
        status: text(item?.status ?? item?.result, "—"),
        detail: text(item?.detail ?? item?.reason ?? item?.message, ""),
      }));
    }

    return Object.entries(source).map(([name, raw]: [string, any], i) => ({
      id: i,
      name,
      status: typeof raw === "string" ? raw : text(raw?.status ?? raw?.result, "—"),
      detail: typeof raw === "object" ? text(raw?.detail ?? raw?.reason ?? raw?.message, "") : "",
    }));
  }, [risk]);

  async function saveConfig() {
    if (!config) return;
    try {
      setSavingConfig(true);
      setConfigSaved(false);
      setError("");
      const response = await fetch(`${API}/ui/risk/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : body?.reason || "Unable to save risk configuration.",
        );
      }
      setConfig(body?.config ?? config);
      setConfigSaved(true);
      window.setTimeout(() => setConfigSaved(false), 2200);
    } catch (e: any) {
      setError(e?.message || "Unable to save risk configuration.");
    } finally {
      setSavingConfig(false);
    }
  }

  return (
    <Shell>
      <div className="topbar">
        <div className="row" style={{ gap: 12 }}>
          <div className="risk-page-icon"><ShieldIcon /></div>
          <div>
            <div className="eyebrow">Trading</div>
            <h1>Risk</h1>
            <p className="small" style={{ marginTop: 5 }}>
              Guardrails, limits, exposure, and the current trading gate.
            </p>
          </div>
        </div>

        <span className={`pill ${tone(tradingAllowed ? "APPROVED" : "BLOCKED")}`}>
          {tradingAllowed ? "TRADING ALLOWED" : "TRADING BLOCKED"}
        </span>
      </div>

      {error ? <div className="error risk-message">{error}</div> : null}

      <section className="risk-hero card">
        <div className="risk-hero-icon"><ShieldIcon /></div>
        <div className="risk-hero-copy">
          <div className="eyebrow">Current risk decision</div>
          <h2>{state}</h2>
          <p>{reason}</p>
        </div>
        <span className={`pill ${tone(decision)}`}>{decision}</span>
      </section>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
          gap: 12,
          marginTop: 12,
        }}
      >
        <Metric
          label="Daily loss"
          value={money(dailyLoss)}
          helper={
            dailyLossLimit === null
              ? "Limit —"
              : `Limit ${money(dailyLossLimit)}`
          }
          status={
            dailyLossPct !== null
              ? dailyLossPct >= 80
                ? "WARNING"
                : "OK"
              : undefined
          }
        />

        <Metric
          label="Drawdown"
          value={pct(drawdown)}
          helper={
            maxDrawdown === null
              ? "Limit —"
              : `Limit ${pct(maxDrawdown)}`
          }
          status={
            drawdownUsed !== null
              ? drawdownUsed >= 80
                ? "WARNING"
                : "OK"
              : undefined
          }
        />

        <Metric
          label="Risk / trade"
          value={pct(riskPerTrade)}
          helper="Backend value"
        />

        <Metric
          label="Open positions"
          value={
            openPositions === null
              ? "—"
              : String(openPositions)
          }
          helper="Current count"
        />

        <Metric
          label="Exposure"
          value={money(exposure)}
          helper="Current reported exposure"
        />
      </section>

      <section className="card risk-panel" style={{ marginTop: 12 }}>
        <div className="eyebrow">Risk configuration</div>
        <h2 className="section-title risk-title">Your trading limits</h2>
        <p className="small" style={{ marginBottom: 15 }}>
          These values are stored by the backend and used by the risk calculation layer.
        </p>
        {config ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 12 }}>
              {([
                ["Capital","capital",1000],
                ["Risk / trade","per_trade_risk",100],
                ["Daily risk budget","daily_risk_budget",100],
                ["Weekly risk budget","weekly_risk_budget",100],
                ["Monthly risk budget","monthly_risk_budget",100],
                ["Max concurrent risk","max_concurrent_risk",100],
                ["Max open positions","max_open_positions",1],
                ["Max trades / day","max_trades_per_day",1],
                ["Max drawdown %","max_drawdown_pct",0.1],
              ] as const).map(([label,key,step]) => (
                <label key={key}>
                  {label}
                  <input
                    type="number"
                    min={key === "capital" ? 1 : key.includes("positions") || key.includes("trades") ? 1 : 0}
                    step={step}
                    value={Number((config as any)[key])}
                    onChange={(e) => setConfig({ ...config, [key]: Number(e.target.value) } as RiskConfig)}
                  />
                </label>
              ))}
              <label>
                Square-off time
                <input
                  type="time"
                  value={config.square_off_time}
                  onChange={(e) => setConfig({ ...config, square_off_time: e.target.value })}
                />
              </label>
            </div>
            <div style={{ marginTop: 18 }}>
              <div className="eyebrow">Lot sizes</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 12, marginTop: 10 }}>
                {["NIFTY","BANKNIFTY","FINNIFTY","SENSEX"].map((symbol) => (
                  <label key={symbol}>
                    {symbol}
                    <input
                      type="number" min="1" step="1" value={config.lot_sizes?.[symbol] ?? ""}
                      onChange={(e) => setConfig({ ...config, lot_sizes: { ...config.lot_sizes, [symbol]: Number(e.target.value) } })}
                    />
                  </label>
                ))}
              </div>
            </div>
            <div style={{ marginTop: 18, display: "flex", alignItems: "center", gap: 10 }}>
              <button type="button" onClick={saveConfig} disabled={savingConfig} style={{ padding: "10px 16px", border: 0, borderRadius: 8, cursor: savingConfig ? "default" : "pointer", background: "var(--accent)", color: "white", fontWeight: 800 }}>
                {savingConfig ? "Saving…" : "Save risk configuration"}
              </button>
              {configSaved ? <span className="small">Risk configuration saved.</span> : null}
            </div>
          </>
        ) : (
          <div className="risk-empty"><strong>Loading risk configuration</strong><span>The backend configuration is being loaded.</span></div>
        )}
      </section>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)",
          gap: 12,
          marginTop: 12,
        }}
      >
        <div className="card risk-panel">
          <div className="eyebrow">Risk gates</div>
          <h2 className="section-title risk-title">Pre-trade checks</h2>

          {checks.length ? (
            <div className="risk-check-list">
              {checks.map((check) => (
                <div className="risk-check" key={check.id}>
                  <div className="risk-check-marker">
                    <ShieldIcon />
                  </div>
                  <div>
                    <strong>{check.name}</strong>
                    {check.detail ? <p>{check.detail}</p> : null}
                  </div>
                  <span className={`pill ${tone(check.status)}`}>{check.status.toUpperCase()}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="risk-empty">
              <strong>No individual risk checks returned</strong>
              <span>The backend has not supplied a check-level risk breakdown.</span>
            </div>
          )}
        </div>

        <div className="card risk-panel">
          <div className="eyebrow">Execution safety</div>
          <h2 className="section-title risk-title">Protected by design</h2>

          <div className="risk-safety-box">
            <div className="risk-lock"><LockIcon /></div>
            <div>
              <strong>Live execution remains gated</strong>
              <p>
                Risk is presented as a decision layer. A blocked risk state should prevent downstream execution.
              </p>
            </div>
          </div>

          <div className="risk-detail-row">
            <span>Trading allowed</span>
            <strong>{tradingAllowed ? "YES" : "NO"}</strong>
          </div>
          <div className="risk-detail-row">
            <span>Risk decision</span>
            <strong>{decision}</strong>
          </div>
          <div className="risk-detail-row">
            <span>Refresh</span>
            <strong>{loading ? "Loading…" : "5 sec"}</strong>
          </div>
        </div>
      </section>

      <section className="card risk-note">
        <div className="eyebrow">Risk integrity</div>
        <div className="section-title" style={{ marginTop: 5, marginBottom: 5 }}>
          No invented limits
        </div>
        <div className="small">
          Every limit, exposure figure, gate, and decision on this screen is rendered from the backend risk payload.
          Missing values remain <strong>—</strong>.
        </div>
      </section>
    </Shell>
  );
}