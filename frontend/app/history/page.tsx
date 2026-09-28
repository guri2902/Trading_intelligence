"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "../../components/Shell";
import styles from "./history.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function money(v: unknown) {
  const n = Number(v);
  return Number.isFinite(n) ? `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—";
}

function csv(value: unknown) {
  const s = value == null ? "" : String(value);
  return `"${s.replaceAll('"', '""')}"`;
}

export default function HistoryPage() {
  const [accountId, setAccountId] = useState("default");
  const [records, setRecords] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>({});
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [source, setSource] = useState("ALL");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const params = new URLSearchParams({
        account_id: accountId,
        status,
        source,
        limit: "500",
      });
      if (query) params.set("search", query);
      if (from) params.set("date_from", from);
      if (to) params.set("date_to", to);

      const response = await fetch(`${API}/ui/history?${params}`, { cache: "no-store" });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "History request failed.");
      setRecords(body?.records || []);
      setSummary(body?.summary || {});
      setError("");
    } catch (e: any) {
      setError(e?.message || "History backend unavailable.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [accountId, status, source, query, from, to]);

  const filteredSources = useMemo(
    () => ["ALL", ...Array.from(new Set(records.map((r) => String(r.source || "—"))))],
    [records]
  );

  function exportCsv() {
    const header = ["Timestamp", "Symbol", "Type", "Strike", "Expiry", "Qty", "Entry", "Exit", "P&L", "Status", "Source", "Strategy"];
    const lines = [
      header.map(csv).join(","),
      ...records.map((r) => [
        r.timestamp, r.symbol, r.option_type, r.strike, r.expiry, r.quantity,
        r.entry_price, r.exit_price, r.pnl, r.status, r.source, r.strategy,
      ].map(csv).join(",")),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `paper-history-${accountId}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Shell>
      <div className={styles.page}>
        <header className={styles.header}>
          <div><div className={styles.eyebrow}>Trading · Backend history</div><h1>History</h1><p>Persisted paper trades and fills from the backend. This page no longer relies on placeholder history rows.</p></div>
          <button className={styles.export} onClick={exportCsv} disabled={!records.length}>Export CSV</button>
        </header>

        {error ? <div className={styles.error}>{error}</div> : null}

        <section className={styles.filters}>
          <label>Account<input value={accountId} onChange={(e) => setAccountId(e.target.value)} /></label>
          <label>Search<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Symbol / strategy / position" /></label>
          <label>Status<select value={status} onChange={(e) => setStatus(e.target.value)}><option>ALL</option><option>OPEN</option><option>CLOSED</option></select></label>
          <label>Source<select value={source} onChange={(e) => setSource(e.target.value)}>{filteredSources.map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>From<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label>To<input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        </section>

        <section className={styles.summary}>
          <div><span>Records</span><strong>{records.length}</strong></div>
          <div><span>Winners</span><strong className={styles.win}>{summary.wins ?? 0}</strong></div>
          <div><span>Losers</span><strong className={styles.loss}>{summary.losses ?? 0}</strong></div>
          <div><span>Filtered P&L</span><strong className={(Number(summary.pnl) || 0) < 0 ? styles.loss : styles.win}>{money(summary.pnl)}</strong></div>
        </section>

        <section className={styles.card}>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead><tr><th>Time</th><th>Symbol</th><th>Type</th><th>Strike</th><th>Qty</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Status</th><th>Source</th><th>Reason</th></tr></thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.position_id}>
                    <td>{r.timestamp ? new Date(r.timestamp).toLocaleString("en-IN", { hour12: false }) : "—"}</td>
                    <td><strong>{r.symbol}</strong></td>
                    <td>{r.option_type}</td>
                    <td>{r.strike ?? "—"}</td>
                    <td>{r.quantity ?? "—"}</td>
                    <td>{money(r.entry_price)}</td>
                    <td>{money(r.exit_price)}</td>
                    <td className={(Number(r.pnl) || 0) < 0 ? styles.loss : styles.win}>{money(r.pnl)}</td>
                    <td><span className={r.status === "CLOSED" ? styles.closed : styles.open}>{r.status}</span></td>
                    <td>{r.source || "—"}</td>
                    <td>{r.close_reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!records.length ? <div className={styles.empty}><strong>{loading ? "Loading history…" : "No backend records match these filters."}</strong><span>History is read from the persisted paper-trade database.</span></div> : null}
        </section>
      </div>
    </Shell>
  );
}
