"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "../../components/Shell";
import styles from "./paper.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type OptionQuote = {
  instrument_key?: string;
  trading_symbol?: string;
  strike?: number;
  option_type?: string;
  expiry?: string;
  ltp?: number | null;
  bid?: number | null;
  ask?: number | null;
  bid_qty?: number | null;
  ask_qty?: number | null;
  lot_size?: number | null;
  tick_size?: number | null;
  underlying_ltp?: number | null;
  timestamp?: string | null;
};

type OptionRow = {
  strike: number;
  ce?: OptionQuote | null;
  pe?: OptionQuote | null;
};

type OptionChainResponse = {
  status?: string;
  underlying?: string;
  expiry?: string | null;
  available_expiries?: string[];
  spot?: number | null;
  atm_strike?: number | null;
  contract_count?: number;
  rows?: OptionRow[];
  message?: string | null;
};

type Position = {
  position_id: string;
  symbol: string;
  option_type: string;
  strike: number;
  expiry: string;
  quantity: number;
  entry_price: number;
  mark_price: number;
  stop_loss: number;
  target_1?: number | null;
  target_2?: number | null;
  realized_pnl: number;
  unrealized_pnl: number;
  status: string;
  opened_at: string;
  closed_at?: string | null;
  exit_price?: number | null;
  close_reason?: string | null;
  total_costs: number;
  partial_fill: boolean;
};

function money(value: unknown): string {
  const n = Number(value);
  return Number.isFinite(n) ? `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—";
}

function number(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function pnlClass(value: unknown) {
  const n = number(value) ?? 0;
  return n > 0 ? styles.goodText : n < 0 ? styles.badText : styles.mutedText;
}

function formatTime(value: unknown) {
  if (!value) return "—";
  const d = new Date(String(value));
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString("en-IN", { hour12: false });
}

function Icon({ kind }: { kind: "lock" | "refresh" | "close" | "plus" | "mark" }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  if (kind === "lock") return <svg {...common}><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>;
  if (kind === "refresh") return <svg {...common}><path d="M20 11a8 8 0 0 0-14.5-4.5L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.5 4.5L20 16"/><path d="M20 20v-4h-4"/></svg>;
  if (kind === "close") return <svg {...common}><path d="m7 7 10 10M17 7 7 17"/></svg>;
  if (kind === "plus") return <svg {...common}><path d="M12 5v14M5 12h14"/></svg>;
  return <svg {...common}><path d="M5 12h14M13 6l6 6-6 6"/></svg>;
}

export default function PaperPage() {
  const [accountId, setAccountId] = useState("default");
  const [startingEquity, setStartingEquity] = useState("100000");
  const [status, setStatus] = useState<any>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [fills, setFills] = useState<any[]>([]);
  const [curve, setCurve] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [underlying, setUnderlying] = useState("NIFTY");
  const [optionType, setOptionType] = useState<"CE" | "PE">("CE");
  const [expiry, setExpiry] = useState("");
  const [strike, setStrike] = useState("");
  const [quantity, setQuantity] = useState("");
  const [entryPrice, setEntryPrice] = useState("");
  const [symbol, setSymbol] = useState("");
  const [selectedQuote, setSelectedQuote] = useState<OptionQuote | null>(null);
  const [chain, setChain] = useState<OptionChainResponse | null>(null);
  const [chainLoading, setChainLoading] = useState(false);
  const [stopLoss, setStopLoss] = useState("");
  const [target1, setTarget1] = useState("");
  const [target2, setTarget2] = useState("");

  const [markPrices, setMarkPrices] = useState<Record<string, string>>({});

  async function request(path: string, options?: RequestInit) {
    const response = await fetch(`${API}${path}`, {
      cache: "no-store",
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {}),
      },
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail || body || "Request failed."));
    }
    return body;
  }

  async function load(showNotice = false) {
    try {
      const [health, account, positionBody, fillBody, curveBody] = await Promise.all([
        request("/paper/health"),
        request(`/paper/account?account_id=${encodeURIComponent(accountId)}`),
        request(`/paper/positions?account_id=${encodeURIComponent(accountId)}&status=ALL`),
        request(`/paper/fills?account_id=${encodeURIComponent(accountId)}&limit=50`),
        request(`/paper/equity-curve?account_id=${encodeURIComponent(accountId)}`),
      ]);

      setStatus({ health, account });
      setPositions(positionBody?.positions || []);
      setFills(fillBody?.fills || []);
      setCurve(curveBody?.points || []);
      setError("");
      if (showNotice) setNotice("Paper state refreshed from backend.");
    } catch (e: any) {
      setError(e?.message || "Paper backend unavailable.");
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(() => load(), 5000);
    return () => window.clearInterval(timer);
  }, [accountId]);

  const underlyingKeys: Record<string, string> = {
    NIFTY: "NSE_INDEX|Nifty 50",
    BANKNIFTY: "NSE_INDEX|Nifty Bank",
    FINNIFTY: "NSE_INDEX|Nifty Fin Service",
    SENSEX: "BSE_INDEX|SENSEX",
  };

  async function loadOptionChain(nextExpiry?: string) {
    setChainLoading(true);
    try {
      const params = new URLSearchParams({
        underlying,
        underlying_key: underlyingKeys[underlying],
        strike_window: "30",
      });
      if (nextExpiry) params.set("expiry_date", nextExpiry);

      const body = await request(`/ui/option-chain?${params.toString()}`);
      setChain(body || null);
      const expiries = Array.isArray(body?.available_expiries) ? body.available_expiries : [];
      const selected = nextExpiry || body?.expiry || expiries[0] || "";
      setExpiry(selected);
      setError("");
      if (body?.status === "ERROR") {
        setError(body?.message || "Unable to load Upstox option chain.");
      }
    } catch (e: any) {
      setChain(null);
      setError(e?.message || "Unable to load Upstox option chain.");
    } finally {
      setChainLoading(false);
    }
  }

  useEffect(() => {
    setExpiry("");
    setStrike("");
    setSelectedQuote(null);
    setSymbol("");
    setQuantity("");
    setEntryPrice("");
    loadOptionChain();
  }, [underlying]);

  useEffect(() => {
    const rows = Array.isArray(chain?.rows) ? chain.rows : [];
    if (!rows.length) {
      setSelectedQuote(null);
      return;
    }

    const currentStrike = Number(strike);
    const available = rows.map((row) => row.strike).filter((value) => Number.isFinite(value));
    const nextStrike = Number.isFinite(currentStrike) && available.includes(currentStrike)
      ? currentStrike
      : (chain?.atm_strike && available.includes(Number(chain.atm_strike)) ? Number(chain.atm_strike) : available[0]);

    if (Number.isFinite(nextStrike)) {
      setStrike(String(nextStrike));
    }
  }, [chain]);

  const selectedRow = useMemo(() => {
    const rows = Array.isArray(chain?.rows) ? chain.rows : [];
    const selectedStrike = Number(strike);
    return rows.find((row) => row.strike === selectedStrike) || null;
  }, [chain, strike]);

  useEffect(() => {
    const quote = optionType === "CE" ? selectedRow?.ce : selectedRow?.pe;
    setSelectedQuote(quote || null);

    if (!quote) {
      setSymbol("");
      setEntryPrice("");
      setQuantity("");
      return;
    }

    setSymbol(quote.instrument_key || quote.trading_symbol || "");
    const buyPrice = Number(quote.ask ?? quote.ltp);
    if (Number.isFinite(buyPrice) && buyPrice > 0) setEntryPrice(String(buyPrice));
    const lotSize = Number(quote.lot_size);
    if (Number.isFinite(lotSize) && lotSize > 0) setQuantity(String(lotSize));
  }, [selectedRow, optionType]);

  async function ensureAccount() {
    setBusy(true);
    try {
      const body = await request("/paper/account", {
        method: "POST",
        body: JSON.stringify({
          account_id: accountId,
          starting_equity: Number(startingEquity),
        }),
      });
      setNotice(`Simulation account ${body.account_id} is ready.`);
      await load();
    } catch (e: any) {
      setError(e?.message || "Unable to initialize paper account.");
    } finally {
      setBusy(false);
    }
  }

  async function submitOrder() {
    setBusy(true);
    setError("");
    setNotice("");

    if (!symbol || !strike || !expiry || !entryPrice || !stopLoss || !quantity) {
      setError("Select a live Upstox option and provide quantity and stop-loss.");
      setBusy(false);
      return;
    }

    try {
      const body = await request("/paper/orders", {
        method: "POST",
        body: JSON.stringify({
          account_id: accountId,
          symbol,
          action: optionType === "CE" ? "BUY_CE" : "BUY_PE",
          option_type: optionType,
          strike: Number(strike),
          expiry,
          quantity: Number(quantity),
          entry_price: Number(entryPrice),
          stop_loss: Number(stopLoss),
          target_1: target1 ? Number(target1) : null,
          target_2: target2 ? Number(target2) : null,
          timestamp: selectedQuote?.timestamp || undefined,
          bid: number(selectedQuote?.bid),
          ask: number(selectedQuote?.ask),
          available_quantity: number(selectedQuote?.ask_qty),
          source: "paper_upstox",
        }),
      });

      setNotice(`Paper order ${body.status.toLowerCase()} · position ${body.position.position_id}.`);
      await load();
    } catch (e: any) {
      setError(e?.message || "Paper order rejected.");
    } finally {
      setBusy(false);
    }
  }

  async function markManual(position: Position) {
    const price = markPrices[position.position_id];
    if (!price) {
      setError(`Enter a mark price for ${position.symbol}.`);
      return;
    }

    setBusy(true);
    try {
      const body = await request(`/paper/positions/${position.position_id}/mark`, {
        method: "POST",
        body: JSON.stringify({
          account_id: accountId,
          position_id: position.position_id,
          price: Number(price),
        }),
      });
      setNotice(`Marked ${position.symbol} at ${money(body.position.mark_price)}.`);
      await load();
    } catch (e: any) {
      setError(e?.message || "Manual mark failed.");
    } finally {
      setBusy(false);
    }
  }

  async function markLatest(position: Position) {
    setBusy(true);
    try {
      const body = await request(`/paper/positions/${position.position_id}/mark-latest`, {
        method: "POST",
        body: JSON.stringify({ account_id: accountId }),
      });
      setNotice(`Marked from persisted market snapshot · ${formatTime(body.snapshot_time)}.`);
      await load();
    } catch (e: any) {
      setError(e?.message || "No backend market snapshot is available for this position.");
    } finally {
      setBusy(false);
    }
  }

  async function close(position: Position) {
    const price = markPrices[position.position_id];
    if (!price) {
      setError(`Enter the exit price for ${position.symbol} before closing.`);
      return;
    }

    setBusy(true);
    try {
      await request(`/paper/positions/${position.position_id}/close`, {
        method: "POST",
        body: JSON.stringify({
          account_id: accountId,
          position_id: position.position_id,
          exit_price: Number(price),
          reason: "MANUAL_CLOSE",
          timestamp: new Date().toISOString(),
        }),
      });
      setNotice(`${position.symbol} closed in simulation.`);
      await load();
    } catch (e: any) {
      setError(e?.message || "Close failed.");
    } finally {
      setBusy(false);
    }
  }

  const account = status?.account || {};
  const openPositions = useMemo(() => positions.filter((p) => p.status === "OPEN"), [positions]);
  const todayPnl = number(status?.today_virtual_pnl);
  const maxPoint = curve.reduce((max, point) => Math.max(max, Number(point.equity) || 0), Number(account.starting_equity) || 0);

  return (
    <Shell>
      <div className={styles.page}>
        <header className={styles.header}>
          <div>
            <div className={styles.eyebrow}>Trading · Simulation</div>
            <h1>Paper Trading</h1>
            <p>Backend-backed virtual execution using the Phase 19 account engine and Phase 20 execution simulator.</p>
          </div>
          <div className={styles.simBadge}><Icon kind="lock" /> SIMULATION ONLY</div>
        </header>

        {error ? <div className={styles.error}>{error}</div> : null}
        {notice ? <div className={styles.notice}>{notice}</div> : null}

        <section className={styles.statusGrid}>
          <div className={styles.metric}><span>Backend</span><strong className={styles.goodText}>{status?.health?.status === "ok" ? "CONNECTED" : "—"}</strong></div>
          <div className={styles.metric}><span>Account</span><strong>{account.account_id || accountId}</strong></div>
          <div className={styles.metric}><span>Virtual equity</span><strong>{money(account.equity)}</strong></div>
          <div className={styles.metric}><span>Today P&L</span><strong className={pnlClass(todayPnl)}>{money(todayPnl)}</strong></div>
          <div className={styles.metric}><span>Open positions</span><strong>{status?.open_positions ?? openPositions.length}</strong></div>
        </section>

        <section className={styles.mainGrid}>
          <div>
            <section className={styles.card}>
              <div className={styles.sectionHead}>
                <div><div className={styles.eyebrow}>Account</div><h2>Virtual account</h2></div>
                <button className={styles.secondaryButton} onClick={() => load(true)} disabled={busy}>{Icon({ kind: "refresh" })} Refresh</button>
              </div>
              <div className={styles.two}>
                <label>Account ID<input value={accountId} onChange={(e) => setAccountId(e.target.value)} /></label>
                <label>Starting equity<input type="number" min="1" value={startingEquity} onChange={(e) => setStartingEquity(e.target.value)} /></label>
              </div>
              <button className={styles.primaryButton} onClick={ensureAccount} disabled={busy}>{Icon({ kind: "plus" })} Initialize / ensure account</button>
            </section>

            <section className={styles.card}>
              <div className={styles.sectionHead}>
                <div><div className={styles.eyebrow}>Upstox market data</div><h2>Open simulated option</h2></div>
                <button className={styles.secondaryButton} onClick={() => loadOptionChain(expiry || undefined)} disabled={busy || chainLoading}>{chainLoading ? "Loading…" : "Refresh chain"}</button>
              </div>

              <div className={styles.two}>
                <label>Underlying
                  <select value={underlying} onChange={(e) => setUnderlying(e.target.value)}>
                    <option value="NIFTY">NIFTY</option>
                    <option value="BANKNIFTY">BANKNIFTY</option>
                    <option value="FINNIFTY">FINNIFTY</option>
                    <option value="SENSEX">SENSEX</option>
                  </select>
                </label>
                <label>Expiry
                  <select value={expiry} onChange={(e) => loadOptionChain(e.target.value)} disabled={chainLoading || !(chain?.available_expiries?.length)}>
                    {(chain?.available_expiries || []).map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </label>
                <label>Option type
                  <select value={optionType} onChange={(e) => setOptionType(e.target.value as "CE" | "PE")}>
                    <option>CE</option><option>PE</option>
                  </select>
                </label>
                <label>Strike
                  <select value={strike} onChange={(e) => setStrike(e.target.value)} disabled={!chain?.rows?.length}>
                    {(chain?.rows || []).map((row) => <option key={row.strike} value={row.strike}>{row.strike}{row.strike === Number(chain?.atm_strike) ? " · ATM" : ""}</option>)}
                  </select>
                </label>
                <label>Quantity
                  <input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
                </label>
                <label>Entry price
                  <input type="number" min="0.05" step="0.05" value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} />
                </label>
                <label>Stop loss
                  <input type="number" min="0.05" step="0.05" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} placeholder="Required" />
                </label>
                <label>Target 1
                  <input type="number" min="0.05" step="0.05" value={target1} onChange={(e) => setTarget1(e.target.value)} />
                </label>
                <label>Target 2
                  <input type="number" min="0.05" step="0.05" value={target2} onChange={(e) => setTarget2(e.target.value)} />
                </label>
              </div>

              <div className={styles.help}>
                {selectedQuote ? `Selected ${selectedQuote.trading_symbol || symbol} · LTP ${money(selectedQuote.ltp)} · Ask ${money(selectedQuote.ask)} · Lot ${selectedQuote.lot_size || "—"}` : "Select an option from the Upstox chain."}
              </div>
              <button className={styles.primaryButton} onClick={submitOrder} disabled={busy || !selectedQuote}>{busy ? "Submitting…" : "Open paper position"}</button>
              <div className={styles.help}>Execution remains simulation-only. The backend receives the selected Upstox instrument, quote, and available quantity; no live broker order is sent.</div>
            </section>

            <section className={styles.card}>
              <div className={styles.sectionHead}>
                <div><div className={styles.eyebrow}>Positions</div><h2>Open & closed</h2></div>
                <span className={styles.small}>{positions.length} records</span>
              </div>

              {positions.length ? (
                <div className={styles.positionList}>
                  {positions.map((position) => {
                    const open = position.status === "OPEN";
                    return (
                      <article className={styles.position} key={position.position_id}>
                        <div className={styles.positionTop}>
                          <div>
                            <strong>{position.symbol}</strong>
                            <span>{position.option_type} · {position.strike} · {position.expiry}</span>
                          </div>
                          <span className={`${styles.status} ${open ? styles.active : styles.closed}`}>{position.status}</span>
                        </div>

                        <div className={styles.positionStats}>
                          <div><span>Qty</span><b>{position.quantity}</b></div>
                          <div><span>Entry</span><b>{money(position.entry_price)}</b></div>
                          <div><span>Mark</span><b>{money(position.mark_price)}</b></div>
                          <div><span>P&L</span><b className={pnlClass(position.unrealized_pnl || position.realized_pnl)}>{money(open ? position.unrealized_pnl : position.realized_pnl - position.total_costs)}</b></div>
                          <div><span>Costs</span><b>{money(position.total_costs)}</b></div>
                        </div>

                        {open ? (
                          <div className={styles.positionActions}>
                            <input value={markPrices[position.position_id] || ""} onChange={(e) => setMarkPrices((current) => ({ ...current, [position.position_id]: e.target.value }))} placeholder="Mark / exit price" />
                            <button className={styles.secondaryButton} onClick={() => markLatest(position)} disabled={busy}>{Icon({ kind: "mark" })} Latest snapshot</button>
                            <button className={styles.secondaryButton} onClick={() => markManual(position)} disabled={busy}>Mark</button>
                            <button className={styles.closeButton} onClick={() => close(position)} disabled={busy}>{Icon({ kind: "close" })} Close</button>
                          </div>
                        ) : (
                          <div className={styles.closedMeta}>Closed {formatTime(position.closed_at)} · {position.close_reason || "—"}</div>
                        )}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className={styles.empty}>No paper positions yet. Initialize the account and open a simulated option position above.</div>
              )}
            </section>
          </div>

          <aside className={styles.side}>
            <section className={styles.card}>
              <div className={styles.eyebrow}>Equity</div>
              <h2>Virtual equity</h2>
              {curve.length ? (
                <div className={styles.equityGraph}>
                  {curve.map((point, index) => (
                    <div
                      key={index}
                      className={styles.equityBar}
                      style={{
                        height: `${Math.max(5, ((Number(point.equity) || 0) / Math.max(maxPoint, 1)) * 100)}%`,
                      }}
                      title={`${formatTime(point.timestamp)} · ${money(point.equity)}`}
                    />
                  ))}
                </div>
              ) : <div className={styles.empty}>No equity events yet.</div>}
            </section>

            <section className={styles.card}>
              <div className={styles.eyebrow}>Fill log</div>
              <h2>Recent execution</h2>
              {fills.length ? (
                <div className={styles.fillList}>
                  {fills.slice(0, 12).map((fill, index) => (
                    <div className={styles.fill} key={`${fill.position_id}-${fill.timestamp}-${index}`}>
                      <div>
                        <strong>{fill.symbol}</strong>
                        <span>{formatTime(fill.timestamp)}</span>
                      </div>
                      <div>
                        <b className={fill.side === "SELL" ? styles.badText : styles.goodText}>{fill.side}</b>
                        <span>{money(fill.price)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : <div className={styles.empty}>No fills recorded.</div>}
            </section>

            <section className={styles.safety}>
              <div className={styles.lock}><Icon kind="lock" /></div>
              <div>
                <strong>Execution safety</strong>
                <p>Every order on this screen routes into the simulation engine only. The paper API reports <b>live_execution: false</b>.</p>
              </div>
            </section>
          </aside>
        </section>
      </div>
    </Shell>
  );
}