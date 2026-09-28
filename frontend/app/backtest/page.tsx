"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "../../components/Shell";
import styles from "./backtest.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Strategy = {
  id: string;
  name: string;
  engine_strategy?: string | null;
  status?: string;
  source?: string;
  rules?: {
    legs?: Array<{
      action: "BUY" | "SELL";
      option_type: "CE" | "PE";
      expiry_mode?: "AUTO" | "NEAREST" | "SPECIFIC";
      expiry?: string | null;
      strike_mode?: "ATM" | "ATM_PLUS" | "ATM_MINUS" | "SPECIFIC";
      strike?: number | null;
      strike_offset?: number;
      lots?: number;
    }>;
  };
};

function finite(v: unknown): number | null {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function money(v: unknown): string {
  const n = finite(v);
  return n === null ? "—" : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function pct(v: unknown): string {
  const n = finite(v);
  return n === null ? "—" : `${n.toFixed(2)}%`;
}

function number(v: unknown): string {
  const n = finite(v);
  return n === null ? "—" : n.toFixed(2);
}

function tone(v: unknown) {
  const s = String(v ?? "").toUpperCase();
  if (["READY", "PASS", "QUALIFIED", "APPROVED", "OK"].includes(s)) return styles.good;
  if (["FAIL", "FAILED", "ERROR", "BLOCKED", "DISABLED"].includes(s)) return styles.bad;
  if (["WAIT", "PENDING", "SKIPPED"].includes(s)) return styles.warn;
  return styles.neutral;
}

function EquityChart({ curve, trades }: { curve: any[]; trades: any[] }) {
  const source = curve.length
    ? curve.map((x) => finite(x?.equity ?? x?.value)).filter((x): x is number => x !== null)
    : trades.reduce((values: number[], t: any) => {
        const pnl = finite(t?.net_pnl ?? t?.pnl) ?? 0;
        values.push((values.at(-1) ?? 0) + pnl);
        return values;
      }, []);

  if (!source.length) {
    return <div className={styles.emptyInner}>No equity series returned by the backend.</div>;
  }

  const min = Math.min(0, ...source);
  const max = Math.max(0, ...source);
  const span = Math.max(max - min, 1);

  const points = source
    .map((v, i) => {
      const x = (i / Math.max(source.length - 1, 1)) * 100;
      const y = 90 - ((v - min) / span) * 80;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className={styles.chartWrap}>
      <div className={styles.chartLegend}>
        <span>Peak {money(max)}</span>
        <span>Low {money(min)}</span>
      </div>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className={styles.chart}>
        <line x1="0" y1="90" x2="100" y2="90" className={styles.axis} vectorEffect="non-scaling-stroke" />
        <polyline points={points} className={styles.equityLine} vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategyId, setStrategyId] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [barsLimit, setBarsLimit] = useState(2500);

  const [strikeReference, setStrikeReference] = useState("");
  const [expiry, setExpiry] = useState("");
  const [strikeMode, setStrikeMode] = useState("ATM");
  const [strikeOffset, setStrikeOffset] = useState(0);

  const [stopPct, setStopPct] = useState(0.15);
  const [targetRR, setTargetRR] = useState(1.5);
  const [capital, setCapital] = useState(100000);
  const [quantity, setQuantity] = useState(1);
  const [slippage, setSlippage] = useState(5);

  const [rows, setRows] = useState<any[]>([]);
  const [result, setResult] = useState<any>(null);
  const [resultTab, setResultTab] = useState<"overview" | "trades" | "oos" | "robustness" | "regime" | "quality">("overview");
  const [loading, setLoading] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadStrategies() {
      try {
        const [savedResponse, engineResponse] = await Promise.all([
          fetch(`${API}/strategy-studio/strategies`, { cache: "no-store" }),
          fetch(`${API}/strategy-studio/engine-strategies`, { cache: "no-store" }),
        ]);

        const savedBody = savedResponse.ok ? await savedResponse.json() : { strategies: [] };
        const engineBody = engineResponse.ok ? await engineResponse.json() : { strategies: [] };

        const saved: Strategy[] = Array.isArray(savedBody?.strategies) ? savedBody.strategies : [];
        const engineRaw = Array.isArray(engineBody?.strategies) ? engineBody.strategies : [];

        const builtIns: Strategy[] = engineRaw.map((x: any, index: number) => {
          if (typeof x === "string") {
            return {
              id: `builtin-${x.toLowerCase()}`,
              name: x.replaceAll("_", " "),
              engine_strategy: x,
              status: "ACTIVE",
              source: "BUILT_IN",
            };
          }

          const engine = String(x.engine_strategy || x.strategy || x.name || `ENGINE_${index}`).toUpperCase();
          return {
            id: String(x.id || `builtin-${engine.toLowerCase()}`),
            name: String(x.name || x.engine_strategy || x.strategy || engine),
            engine_strategy: engine,
            status: "ACTIVE",
            source: "BUILT_IN",
          };
        });

        const all: Strategy[] = [];
        const seen = new Set<string>();

        for (const item of [...saved, ...builtIns]) {
          const key = item.id || item.engine_strategy || item.name;
          if (seen.has(key)) continue;
          seen.add(key);
          all.push(item);
        }

        setStrategies(all);

        const query = new URLSearchParams(window.location.search);
        const wanted = query.get("strategy");
        const found = all.find((s) => String(s.id) === wanted || String(s.engine_strategy) === wanted);

        if (found) {
          setStrategyId(found.id);
        } else if (all[0]) {
          setStrategyId(all[0].id);
        }
      } catch {
        setError("Unable to load strategies from the Strategy Studio backend.");
      }
    }

    loadStrategies();
  }, []);

  const selected = useMemo(
    () => strategies.find((strategy) => strategy.id === strategyId) || null,
    [strategies, strategyId]
  );

  const selectedLegs = useMemo(
    () => Array.isArray(selected?.rules?.legs) ? selected.rules.legs : [],
    [selected]
  );

  async function loadData() {
    setError("");
    setStatus("");

    if (!fromDate || !toDate) {
      setError("Choose both From and To dates.");
      return;
    }

    setLoadingData(true);
    setStatus("Loading persisted NIFTY 5-minute history…");

    try {
      const ingestParams = new URLSearchParams({
        provider: "upstox",
        instrument_key: "NSE_INDEX|Nifty 50",
        canonical_key: "NSE_INDEX|Nifty 50",
        unit: "minutes",
        interval: "5",
        from_date: fromDate,
        to_date: toDate,
      });

      const ingest = await fetch(`${API}/phase5/ingest/candles?${ingestParams}`, {
        method: "POST",
        cache: "no-store",
      });

      const ingestBody = await ingest.json().catch(() => null);
      if (!ingest.ok) {
        throw new Error(
          typeof ingestBody?.detail === "string"
            ? ingestBody.detail
            : "Historical candle ingestion failed."
        );
      }

      const query = new URLSearchParams({
        canonical_key: "NSE_INDEX|Nifty 50",
        timeframe: "minutes:5",
        limit: String(Math.max(30, barsLimit)),
        from_date: fromDate,
        to_date: toDate,
      });

      const response = await fetch(`${API}/phase5/candles/latest?${query}`, {
        cache: "no-store",
      });
      const body = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : "Persisted candle query failed."
        );
      }

      const loaded = Array.isArray(body) ? body : body?.rows || body?.value || [];
      if (!loaded.length) {
        throw new Error("No persisted NIFTY candles were returned for that date range.");
      }

      setRows(loaded);

      if (!strikeReference) {
        const close = finite(loaded.at(-1)?.close);
        if (close !== null) setStrikeReference(String(Math.round(close)));
      }

      setStatus(`${loaded.length} bars loaded · ${loaded[0]?.timestamp || "—"} → ${loaded.at(-1)?.timestamp || "—"}`);
    } catch (e: any) {
      setRows([]);
      setStatus("");
      setError(e?.message || "Historical data load failed.");
    } finally {
      setLoadingData(false);
    }
  }

  async function runBacktest() {
    setError("");
    setStatus("");
    setResult(null);
    setResultTab("overview");

    if (!selected) {
      setError("Select a strategy.");
      return;
    }

    if (!selected.engine_strategy && selectedLegs.length === 0) {
      setError("This strategy does not have a deterministic StrategyEngine mapping required for the Upstox historical option backtest.");
      return;
    }

    if (rows.length < 30) {
      setError("Load historical data first. At least 30 bars are required.");
      return;
    }

    if (!strikeReference) {
      setError("Enter a strike reference or load data again to populate one.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API}/backtest/upstox/research-suite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          underlying_rows: rows,
          strategy_name: selected.name,
          preferred_strategy: selected.engine_strategy,
          strike_reference: Number(strikeReference),
          expiry: expiry || null,
          strike_mode: strikeMode,
          strike_offset: Number(strikeOffset),
          stop_pct: Number(stopPct),
          target_rr: Number(targetRR),
          config: {
            initial_capital: Number(capital),
            quantity: Math.max(1, Number(quantity)),
            slippage_bps: Number(slippage),
            latency_bars: 1,
            max_trades: null,
          },
          monte_carlo_simulations: 1000,
          monte_carlo_seed: 42,
        }),
      });

      const body = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : JSON.stringify(body?.detail || body || "Upstox backtest failed.")
        );
      }

      setResult(body);
      setStatus("Upstox backtest completed. Review the diagnostics before treating a result as valid.");

      if (!body?.base_backtest?.selection) {
        setError("The Upstox backtest returned no selected historical option contract. This result is not valid as an actual-option backtest.");
      }
    } catch (e: any) {
      setStatus("");
      setError(e?.message || "Upstox backtest failed.");
    } finally {
      setLoading(false);
    }
  }

  const base = result?.base_backtest || {};
  const metrics = base?.metrics || {};
  const trades = Array.isArray(base?.trades) ? base.trades : [];
  const curve = Array.isArray(base?.equity_curve) ? base.equity_curve : [];

  const selection = base?.selection || null;
  const selectedContract =
    selection?.last_contract ||
    (Array.isArray(selection?.contracts) ? selection.contracts.at(-1) : null) ||
    null;

  const diagnostics = base?.diagnostics || {};

  const oos = result?.walkforward?.oos_summary || {};
  const robustness = result?.robustness || {};
  const regime = result?.regime?.regime_analysis || {};
  const quality = result?.quality || {};
  const qualification = result?.qualification || {};

  const selectedContracts = Array.isArray(selection?.contracts)
    ? selection.contracts
    : [];
  const hasActualContracts =
    Boolean(selectedContract?.instrument_key) ||
    selectedContracts.some((contract: any) => Boolean(contract?.instrument_key));

  const resultValid =
    Boolean(result) &&
    hasActualContracts &&
    Number(diagnostics?.option_bars_loaded || 0) > 0;

  const contractText = selectedContract
    ? `${selectedContract.underlying_symbol || "NIFTY"} · ${selectedContract.expiry || "—"} · ${selectedContract.strike ?? "—"} ${selectedContract.option_type || "—"}`
    : "No historical option contract selected";
  const lotSize = Number(selectedContract?.lot_size || 0) || null;
  const quantityLots = Number(selectedContract?.quantity_lots || quantity || 1) || 1;
  const quantityUnits = Number(selectedContract?.quantity_units || (lotSize ? lotSize * quantityLots : 0)) || null;

  return (
    <Shell>
      <div className={styles.page}>
        <header className={styles.header}>
          <div>
            <div className={styles.eyebrow}>Research Studio</div>
            <h1>Backtest</h1>
            <p>
              Upstox historical NIFTY candles + actual expired option prices → strategy → P&L → walk-forward → robustness → regime → quality.
            </p>
          </div>
          <div className={`${styles.modeBadge} ${styles.actual}`}>
            UPSTOX · ACTUAL HISTORICAL PRICES
          </div>
        </header>

        <div className={styles.workspace}>
          <aside className={styles.config}>
            <section className={styles.card}>
              <div className={styles.eyebrow}>01 · Setup</div>
              <h2>Research run</h2>

              <label>
                Strategy
                <select value={strategyId} onChange={(e) => {
                  setStrategyId(e.target.value);
                }}>
                  <option value="">Select strategy</option>
                  {strategies.map((strategy) => (
                    <option key={strategy.id} value={strategy.id}>
                      {strategy.name}{strategy.engine_strategy ? ` · ${strategy.engine_strategy}` : " · CUSTOM"}
                    </option>
                  ))}
                </select>
              </label>
            </section>

            <section className={styles.card}>
              <div className={styles.eyebrow}>02 · Data</div>
              <h2>Historical window</h2>

              <div className={styles.two}>
                <label>From<input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} /></label>
                <label>To<input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} /></label>
              </div>

              <label>
                Max bars
                <input type="number" min={30} max={50000} value={barsLimit} onChange={(e) => setBarsLimit(Number(e.target.value))} />
              </label>

              <button className={styles.secondaryButton} onClick={loadData} disabled={loadingData || loading}>
                {loadingData ? "Loading…" : "Load historical data"}
              </button>

              <div className={styles.dataStatus}>
                <span className={`${styles.pill} ${rows.length >= 30 ? styles.good : styles.warn}`}>
                  {rows.length} bars ready
                </span>
                {rows.length ? <span>{rows[0]?.timestamp || "—"} → {rows.at(-1)?.timestamp || "—"}</span> : null}
              </div>
            </section>

            {
              <section className={styles.card}>
                <div className={styles.eyebrow}>03 · Options</div>
                <h2>Contract selection</h2>

                <label>
                  Strike reference
                  <input type="number" value={strikeReference} onChange={(e) => setStrikeReference(e.target.value)} placeholder="Loaded close / spot" />
                </label>

                {selectedLegs.length ? (
                  <div className={styles.message}>
                    {selectedLegs.length} saved option legs · contract selection comes from the Strategy Builder.
                  </div>
                ) : (
                  <label>
                    Expiry (optional)
                    <input value={expiry} onChange={(e) => setExpiry(e.target.value)} placeholder="YYYY-MM-DD" />
                  </label>
                )}

                <div className={styles.two}>
                  <label>Strike mode<select value={strikeMode} onChange={(e) => setStrikeMode(e.target.value)}><option>ATM</option><option>OFFSET</option><option>ATM_OFFSET</option></select></label>
                  <label>Offset<input type="number" value={strikeOffset} onChange={(e) => setStrikeOffset(Number(e.target.value))} /></label>
                </div>

                <div className={styles.two}>
                  <label>Stop %<input type="number" step="0.01" min="0.01" value={stopPct} onChange={(e) => setStopPct(Number(e.target.value))} /></label>
                  <label>Target R:R<input type="number" step="0.1" min="0.1" value={targetRR} onChange={(e) => setTargetRR(Number(e.target.value))} /></label>
                </div>
              </section>
              }

              <section className={styles.card}>
              <div className={styles.eyebrow}>04 · Costs</div>
              <h2>Execution assumptions</h2>

              <div className={styles.two}>
                <label>Capital<input type="number" min="1" value={capital} onChange={(e) => setCapital(Number(e.target.value))} /></label>
                <label>Lots<input type="number" min="1" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} /></label>
              </div>
              <div className={styles.dataStatus}>1 lot uses the actual Upstox contract lot size automatically.</div>

              <label>Slippage (bps)<input type="number" min="0" step="0.5" value={slippage} onChange={(e) => setSlippage(Number(e.target.value))} /></label>

              <button className={styles.runButton} disabled={loading || loadingData || !selected || rows.length < 30} onClick={runBacktest}>
                {loading ? "Running research…" : "Run backtest"}
              </button>

              {status ? <div className={styles.message}>{status}</div> : null}
              {error ? <div className={styles.error}>{error}</div> : null}
            </section>
          </aside>

          <main className={styles.results}>
            {!result ? (
              <div className={styles.empty}>
                <div className={styles.emptyIcon}>↗</div>
                <h2>No result yet</h2>
                <p>Select a strategy, choose dates, load historical candles, then run the backtest.</p>
                <div className={styles.flow}>
                  <span>01 Select</span><span>02 Load</span><span>03 Configure</span><span>04 Run</span><span>05 Validate</span>
                </div>
              </div>
            ) : (
              <>
                <section className={styles.resultHero}>
                  <div>
                    <div className={styles.eyebrow}>Research result</div>
                    <h2>{selected?.name || result?.strategy || "Strategy"}</h2>
                    <p>{contractText}</p>
                  </div>
                  <div className={styles.heroBadges}>
                    <span className={`${styles.pill} ${resultValid ? styles.good : styles.bad}`}>
                      {resultValid ? "VALID RESULT" : "INVALID / INCOMPLETE"}
                    </span>
                    <span className={`${styles.pill} ${tone(quality?.classification)}`}>
                      {quality?.classification ? `QUALITY · ${quality.classification}` : "QUALITY · PENDING"}
                    </span>
                  </div>
                </section>

                <section className={styles.metricGrid}>
                  <div className={styles.metric}><span>Net profit</span><strong>{money(metrics.net_profit)}</strong></div>
                  <div className={styles.metric}><span>Win rate</span><strong>{pct(metrics.win_rate_pct)}</strong></div>
                  <div className={styles.metric}><span>Profit factor</span><strong>{number(metrics.profit_factor)}</strong></div>
                  <div className={styles.metric}><span>Max drawdown</span><strong>{pct(metrics.max_drawdown_pct ?? oos.max_drawdown_pct)}</strong></div>
                  <div className={styles.metric}><span>Trades</span><strong>{metrics.total_trades ?? trades.length}</strong></div>
                </section>

                <div className={styles.resultTabs}>
                  {(["overview", "trades", "oos", "robustness", "regime", "quality"] as const).map((item) => (
                    <button key={item} className={resultTab === item ? styles.resultTabActive : styles.resultTab} onClick={() => setResultTab(item)}>
                      {item === "oos" ? "Walk-forward" : item}
                    </button>
                  ))}
                </div>

                {resultTab === "overview" ? (
                  <div className={styles.resultGrid}>
                    <section className={`${styles.card} ${styles.chartCard}`}>
                      <div className={styles.eyebrow}>Performance</div>
                      <h3>Equity curve</h3>
                      <EquityChart curve={curve} trades={trades} />
                    </section>

                    <section className={styles.card}>
                      <div className={styles.eyebrow}>Data integrity</div>
                      <h3>What the engine actually used</h3>
                      <div className={styles.detailList}>
                        <div><span>Provider</span><strong>{result?.provider || result?.data_source || "Upstox"}</strong></div>
                        <div><span>Historical option prices</span><strong>ACTUAL</strong></div>
                        <div><span>Synthetic prices</span><strong>FALSE</strong></div>
                        <div><span>Contract</span><strong>{contractText}</strong></div>
                        <div><span>Lot size</span><strong>{lotSize ?? "—"}</strong></div>
                        <div><span>Backtest size</span><strong>{quantityLots} lot{quantityLots === 1 ? "" : "s"} · {quantityUnits ?? "—"} units</strong></div>
                        <div><span>Signals generated</span><strong>{diagnostics?.signals_generated ?? "—"}</strong></div>
                        <div><span>Executable signals</span><strong>{diagnostics?.signals_executable ?? "—"}</strong></div>
                        <div><span>Option bars loaded</span><strong>{diagnostics?.option_bars_loaded ?? "—"}</strong></div>
                        <div><span>Skipped signals</span><strong>{diagnostics?.signals_skipped ?? "None"}</strong></div>
                        <div><span>Trades executed</span><strong>{metrics?.total_trades ?? trades.length}</strong></div>
                        <div><span>Trade limit</span><strong>{metrics?.trade_limit == null ? "UNLIMITED" : metrics.trade_limit}</strong></div>
                        <div><span>Limit hit</span><strong>{metrics?.trade_limit_hit ? "YES" : "NO"}</strong></div>
                        <div><span>Last trade exit</span><strong>{metrics?.last_trade_exit_time ?? "—"}</strong></div>
                        <div><span>Last processed bar</span><strong>{metrics?.last_processed_bar_time ?? "—"}</strong></div>
                        <div><span>Skip reasons</span><strong>{Object.entries(diagnostics?.skipped_by_reason || {}).map(([key, value]) => `${key}=${value}`).join(" · ") || "None"}</strong></div>
                      </div>
                    </section>
                  </div>
                ) : null}

                {resultTab === "trades" ? (
                  <section className={styles.card}>
                    <div className={styles.eyebrow}>Execution history</div>
                    <h3>Trade list</h3>
                    {trades.length ? (
                      <div className={styles.tableWrap}>
                        <table className={styles.table}>
                          <thead><tr><th>#</th><th>Entry</th><th>Exit</th><th>Direction</th><th>Strike</th><th>Qty</th><th>Entry</th><th>Exit</th><th>Gross</th><th>Costs</th><th>Net P&L</th><th>Reason</th></tr></thead>
                          <tbody>
                            {trades.map((trade: any, index: number) => {
                              const pnl = finite(trade?.net_pnl ?? trade?.pnl);
                              return (
                                <tr key={index}>
                                  <td>{index + 1}</td>
                                  <td>{trade?.entry_time || trade?.entry_timestamp || "—"}</td>
                                  <td>{trade?.exit_time || trade?.exit_timestamp || "—"}</td>
                                  <td>{trade?.direction || "—"}</td>
                                  <td>{trade?.strike ?? selection?.strike ?? "—"}</td>
                                  <td>{trade?.quantity ?? quantityUnits ?? "—"}</td>
                                  <td>{money(trade?.entry_price ?? trade?.filled_entry)}</td>
                                  <td>{money(trade?.exit_price)}</td>
                                  <td>{money(trade?.gross_pnl)}</td>
                                  <td>{money(trade?.costs)}</td>
                                  <td className={pnl !== null && pnl < 0 ? styles.loss : styles.win}>{money(pnl)}</td>
                                  <td>{trade?.exit_reason || "—"}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : <div className={styles.emptyInner}>No trades returned.</div>}
                  </section>
                ) : null}

                {resultTab === "oos" ? (
                  <div className={styles.validationGrid}>
                    <div className={styles.validationCard}><span>Qualification rate</span><strong>{pct(oos.qualification_rate_pct)}</strong></div>
                    <div className={styles.validationCard}><span>OOS net profit</span><strong>{money(oos.aggregate_oos_net_profit)}</strong></div>
                    <div className={styles.validationCard}><span>Windows evaluated</span><strong>{oos.windows_evaluated ?? "—"}</strong></div>
                    <div className={styles.validationCard}><span>OOS trades</span><strong>{oos.aggregate_oos_trades ?? "—"}</strong></div>
                    <div className={styles.validationCard}><span>Windows failed</span><strong>{result?.walkforward?.windows_failed ?? "—"}</strong></div>
                    <div className={styles.validationCard}><span>Lookahead safe</span><strong>{String(result?.regime?.lookahead_safe ?? oos.lookahead_safe ?? "—")}</strong></div>
                  </div>
                ) : null}

                {resultTab === "robustness" ? (
                  <div className={styles.validationGrid}>
                    <div className={styles.validationCard}><span>MC loss probability</span><strong>{pct(robustness?.monte_carlo?.probability_of_loss_pct)}</strong></div>
                    <div className={styles.validationCard}><span>P95 max drawdown</span><strong>{money(robustness?.monte_carlo?.p95_max_drawdown)}</strong></div>
                    <div className={styles.validationCard}><span>MC status</span><strong>{robustness?.monte_carlo?.status ?? "—"}</strong></div>
                    <div className={styles.validationCard}><span>Baseline P&L</span><strong>{money(robustness?.cost_slippage_sensitivity?.baseline?.net_pnl)}</strong></div>
                  </div>
                ) : null}

                {resultTab === "regime" ? (
                  <div className={styles.regimeGrid}>
                    {Object.entries(regime?.regimes || {}).map(([key, value]: any) => (
                      <div className={styles.regimeCard} key={key}>
                        <span>{key}</span>
                        <strong>{value?.trades ?? 0} trades</strong>
                        <small>{money(value?.net_profit)}</small>
                      </div>
                    ))}
                    {!Object.keys(regime?.regimes || {}).length ? <div className={styles.emptyInner}>No regime breakdown returned.</div> : null}
                  </div>
                ) : null}

                {resultTab === "quality" ? (
                  <div className={styles.validationGrid}>
                    <div className={styles.validationCard}><span>Quality score</span><strong>{number(quality?.quality_score)}</strong></div>
                    <div className={styles.validationCard}><span>Classification</span><strong>{quality?.classification ?? "—"}</strong></div>
                    <div className={styles.validationCard}><span>Promotion gate</span><strong>{qualification?.promotion_gate ?? "—"}</strong></div>
                    <div className={styles.validationCard}><span>Active</span><strong>{String(quality?.active ?? "—")}</strong></div>
                    <div className={styles.copyCard}><b>Why active</b><p>{quality?.why_active || "—"}</p></div>
                    <div className={styles.copyCard}><b>When to avoid</b><p>{quality?.when_to_avoid || "—"}</p></div>
                  </div>
                ) : null}
              </>
            )}
          </main>
        </div>
      </div>
    </Shell>
  );
}