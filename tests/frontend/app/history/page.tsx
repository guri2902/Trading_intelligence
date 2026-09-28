"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "../../components/Shell";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Trade = {
  id?: string | number;
  timestamp?: string;
  datetime?: string;
  symbol?: string;
  side?: string;
  action?: string;
  quantity?: number | string;
  price?: number | string;
  entry_price?: number | string;
  exit_price?: number | string;
  pnl?: number | string;
  net_pnl?: number | string;
  status?: string;
  source?: string;
  strategy?: string;
};

function finite(v: any): number | null {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function money(v: any) {
  const n = finite(v);
  return n === null ? "—" : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function sideTone(v: any) {
  const s = String(v ?? "").toUpperCase();
  if (["BUY", "LONG", "CALL"].includes(s)) return "good";
  if (["SELL", "SHORT", "PUT"].includes(s)) return "bad";
  return "neutral";
}

function csvEscape(value: unknown) {
  const text = value == null ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function HistoryIcon() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 7v5h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M4.8 12A7.5 7.5 0 1 0 7 6.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
      <path d="M12 8v4l3 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 4v11M8 11l4 4 4-4M5 20h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export default function HistoryPage() {
  const [rows, setRows] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [side, setSide] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [source, setSource] = useState("ALL");
  const [date, setDate] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const paths = [
          "/paper/fills",
          "/trading/history",
          "/history",
        ];

        let body: any = null;
        for (const path of paths) {
          try {
            const response = await fetch(`${API}${path}`, { cache: "no-store" });
            if (!response.ok) continue;
            const candidate = await response.json();
            body = candidate;
            break;
          } catch {
            // Try next supported endpoint without assuming one exists.
          }
        }

        if (body === null) {
          setError("History endpoint is unavailable.");
          return;
        }

        const items = Array.isArray(body)
          ? body
          : (body.trades || body.fills || body.history || body.rows || body.value || []);

        setRows(Array.isArray(items) ? items : []);
      } catch (e: any) {
        setError(e?.message || "Unable to load trade history.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const sources = useMemo(
    () => ["ALL", ...Array.from(new Set(rows.map(row => String(row.source || "Unknown")))).sort()],
    [rows]
  );

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();

    return rows.filter((row) => {
      const time = String(row.timestamp || row.datetime || "");
      const symbol = String(row.symbol || "");
      const rowSide = String(row.side || row.action || "").toUpperCase();
      const rowStatus = String(row.status || "FILLED").toUpperCase();
      const rowSource = String(row.source || "Unknown");

      if (needle && !`${symbol} ${rowSide} ${row.strategy || ""} ${rowSource}`.toLowerCase().includes(needle)) return false;
      if (side !== "ALL" && rowSide !== side) return false;
      if (status !== "ALL" && rowStatus !== status) return false;
      if (source !== "ALL" && rowSource !== source) return false;
      if (date && !time.startsWith(date)) return false;

      return true;
    });
  }, [rows, search, side, status, source, date]);

  const totals = useMemo(() => {
    const pnl = filtered.reduce((sum, row) => sum + (finite(row.net_pnl ?? row.pnl) ?? 0), 0);
    const wins = filtered.filter(row => (finite(row.net_pnl ?? row.pnl) ?? 0) > 0).length;
    const losses = filtered.filter(row => (finite(row.net_pnl ?? row.pnl) ?? 0) < 0).length;
    return { pnl, wins, losses };
  }, [filtered]);

  function exportCsv() {
    const header = ["Timestamp", "Symbol", "Side", "Quantity", "Price", "Entry", "Exit", "P&L", "Status", "Source", "Strategy"];
    const lines = [
      header.map(csvEscape).join(","),
      ...filtered.map(row => [
        row.timestamp || row.datetime || "",
        row.symbol || "",
        row.side || row.action || "",
        row.quantity ?? "",
        row.price ?? "",
        row.entry_price ?? "",
        row.exit_price ?? "",
        row.net_pnl ?? row.pnl ?? "",
        row.status || "",
        row.source || "",
        row.strategy || "",
      ].map(csvEscape).join(",")),
    ];

    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "trading-history.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Shell>
      <div className="topbar">
        <div className="row" style={{ gap: 12 }}>
          <div className="history-page-icon"><HistoryIcon /></div>
          <div>
            <div className="eyebrow">Trading</div>
            <h1>History</h1>
            <p className="small" style={{ marginTop: 5 }}>
              Review completed actions with filters and a clean export path.
            </p>
          </div>
        </div>

        <button className="btn secondary history-export" onClick={exportCsv} disabled={!filtered.length}>
          <DownloadIcon /> Export CSV
        </button>
      </div>

      {error ? <div className="error history-message">{error}</div> : null}

      <section className="card history-filter-card">
        <div className="history-filters">
          <label>
            Search
            <input placeholder="Symbol, strategy, source…" value={search} onChange={e => setSearch(e.target.value)} />
          </label>
          <label>
            Date
            <input type="date" value={date} onChange={e => setDate(e.target.value)} />
          </label>
          <label>
            Side
            <select value={side} onChange={e => setSide(e.target.value)}>
              <option>ALL</option>
              <option>BUY</option>
              <option>SELL</option>
              <option>LONG</option>
              <option>SHORT</option>
              <option>CALL</option>
              <option>PUT</option>
            </select>
          </label>
          <label>
            Status
            <select value={status} onChange={e => setStatus(e.target.value)}>
              <option>ALL</option>
              <option>FILLED</option>
              <option>CANCELLED</option>
              <option>REJECTED</option>
              <option>CLOSED</option>
            </select>
          </label>
          <label>
            Source
            <select value={source} onChange={e => setSource(e.target.value)}>
              {sources.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
      </section>

      <section className="history-summary">
        <div className="card history-summary-card">
          <span>Filtered trades</span><strong>{filtered.length}</strong>
        </div>
        <div className="card history-summary-card">
          <span>Winners</span><strong className="history-win">{totals.wins}</strong>
        </div>
        <div className="card history-summary-card">
          <span>Losers</span><strong className="history-loss">{totals.losses}</strong>
        </div>
        <div className="card history-summary-card">
          <span>Filtered P&L</span><strong className={totals.pnl < 0 ? "history-loss" : "history-win"}>{money(totals.pnl)}</strong>
        </div>
      </section>

      <section className="card history-table-card">
        <div className="history-table-head">
          <div>
            <div className="eyebrow">Execution log</div>
            <h2 className="section-title" style={{ marginTop: 5 }}>Trade history</h2>
          </div>
          <span className="small">{loading ? "Loading…" : `${filtered.length} of ${rows.length} records`}</span>
        </div>

        {filtered.length ? (
          <div className="table-wrap">
            <table className="table history-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Action</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>P&L</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>Strategy</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row, index) => {
                  const pnl = finite(row.net_pnl ?? row.pnl);
                  const action = row.side || row.action || "—";
                  const state = String(row.status || "FILLED").toUpperCase();

                  return (
                    <tr key={`${row.id ?? "row"}-${index}`}>
                      <td>{row.timestamp || row.datetime || "—"}</td>
                      <td><strong>{row.symbol || "—"}</strong></td>
                      <td>
                        <span className={`pill ${sideTone(action)}`}>
                          {String(action).toUpperCase()}
                        </span>
                      </td>
                      <td>{row.quantity ?? "—"}</td>
                      <td>{money(row.price ?? row.entry_price)}</td>
                      <td className={pnl !== null && pnl < 0 ? "history-loss" : "history-win"}>
                        {money(pnl)}
                      </td>
                      <td><span className="pill neutral">{state}</span></td>
                      <td>{row.source || "—"}</td>
                      <td>{row.strategy || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="history-empty">
            <strong>{loading ? "Loading trade history…" : "No history records match these filters."}</strong>
            <span>
              {error
                ? "Connect the history or paper-trading backend endpoint to populate this screen."
                : "Try clearing one or more filters, or wait for completed trade records."}
            </span>
          </div>
        )}
      </section>

      <div className="note history-integrity">
        History is a record view. It does not manufacture fills, P&L, timestamps, or action states when the backend does not supply them.
      </div>
    </Shell>
  );
}
