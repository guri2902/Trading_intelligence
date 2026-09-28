"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Shell } from "../../components/Shell";
import styles from "./scanner.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function n(v: unknown) {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

function tone(state: string) {
  if (state === "TRIGGERED") return styles.good;
  if (state === "INVALID") return styles.bad;
  if (state === "WATCH") return styles.warn;
  return styles.neutral;
}

function directionTone(value: string) {
  return value === "LONG"
    ? styles.long
    : value === "SHORT"
      ? styles.short
      : styles.neutral;
}

export default function ScannerPage() {
  const [data, setData] = useState<any>(null);
  const [state, setState] = useState("ALL");
  const [sort, setSort] = useState("confidence");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  const startPipelineIfNeeded = useCallback(async () => {
    const statusResponse = await fetch(`${API}/pipeline/status`, {
      cache: "no-store",
    });

    if (!statusResponse.ok) return;

    const pipeline = await statusResponse.json();

    if (!pipeline?.running) {
      setStarting(true);

      try {
        const response = await fetch(`${API}/pipeline/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ interval_seconds: 30 }),
        });

        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(
            typeof body?.detail === "string"
              ? body.detail
              : "Unable to start realtime pipeline.",
          );
        }
      } finally {
        setStarting(false);
      }
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const response = await fetch(
        `${API}/ui/scanner?state=${state}&limit=50`,
        { cache: "no-store" },
      );

      const body = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : "Scanner request failed.",
        );
      }

      setData(body);
      setError("");
    } catch (e: any) {
      setError(e?.message || "Scanner backend unavailable.");
    } finally {
      setLoading(false);
    }
  }, [state]);

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        await startPipelineIfNeeded();
      } catch (e: any) {
        if (mounted) {
          setError(
            e?.message || "Unable to start the realtime market pipeline.",
          );
        }
      }

      if (mounted) {
        await load();
      }
    })();

    const timer = window.setInterval(load, 5000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [load, startPipelineIfNeeded]);

  const rows = useMemo(() => {
    const copy = [...(data?.rows || [])];

    copy.sort((a, b) => {
      if (sort === "confidence") {
        return (
          (n(b.confidence) ?? -1) -
          (n(a.confidence) ?? -1)
        );
      }

      if (sort === "rr") {
        return (
          (n(b.risk_reward) ?? -1) -
          (n(a.risk_reward) ?? -1)
        );
      }

      return String(a.strategy || "").localeCompare(
        String(b.strategy || ""),
      );
    });

    return copy;
  }, [data, sort]);

  const status = data?.status || (loading ? "LOADING" : "WAIT");

  return (
    <Shell>
      <div className={styles.page}>
        <header className={styles.header}>
          <div>
            <div className={styles.eyebrow}>Market Data · Live Setups</div>
            <h1>Scanner</h1>
            <p>
              Every row comes from the live StrategyEngine pipeline. There are
              no placeholder BANKNIFTY/NIFTY rows.
            </p>
          </div>

          <span
            className={`${styles.status} ${
              status === "LIVE"
                ? styles.live
                : status === "MARKET_CLOSED"
                  ? styles.closed
                  : styles.wait
            }`}
          >
            {starting ? "STARTING PIPELINE" : status}
          </span>
        </header>

        <div className={styles.toolbar}>
          <div>
            <span className={styles.regime}>
              Regime: {data?.regime || "—"}
            </span>
            <span className={styles.regime}>
              Triggered: {data?.triggered_count ?? 0}
            </span>
            <span className={styles.regime}>
              Pipeline: {data?.pipeline_running ? "RUNNING" : "STOPPED"}
            </span>
          </div>

          <div className={styles.controls}>
            <select value={state} onChange={(e) => setState(e.target.value)}>
              <option>ALL</option>
              <option>TRIGGERED</option>
              <option>WATCH</option>
              <option>INVALID</option>
              <option>NO_SETUP</option>
            </select>

            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="confidence">Score / confidence</option>
              <option value="rr">Risk : reward</option>
              <option value="strategy">Strategy</option>
            </select>
          </div>
        </div>

        {error ? <div className={styles.error}>{error}</div> : null}

        {data?.message ? (
          <div
            className={
              data.market_open
                ? styles.info
                : styles.closedMessage
            }
          >
            {data.message}
          </div>
        ) : null}

        <section className={styles.card}>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Direction</th>
                  <th>State</th>
                  <th>Score</th>
                  <th>Entry</th>
                  <th>Invalidation</th>
                  <th>Target 1</th>
                  <th>R:R</th>
                  <th>Option</th>
                  <th>Risk</th>
                </tr>
              </thead>

              <tbody>
                {rows.map((row: any, index: number) => (
                  <tr key={`${row.strategy}-${index}`}>
                    <td>
                      <strong>{row.strategy || "—"}</strong>
                      <span>
                        {row.symbol || "NIFTY"} ·{" "}
                        {row.timestamp
                          ? new Date(row.timestamp).toLocaleTimeString(
                              "en-IN",
                            )
                          : "—"}
                      </span>
                    </td>

                    <td>
                      <span
                        className={`${styles.direction} ${directionTone(
                          row.direction,
                        )}`}
                      >
                        {row.direction || "NONE"}
                      </span>
                    </td>

                    <td>
                      <span
                        className={`${styles.state} ${tone(row.state)}`}
                      >
                        {row.state}
                      </span>
                    </td>

                    <td>
                      {n(row.confidence) === null
                        ? "—"
                        : `${n(row.confidence)!.toFixed(1)}`}
                    </td>

                    <td>{n(row.entry)?.toFixed(2) || "—"}</td>
                    <td>{n(row.invalidation)?.toFixed(2) || "—"}</td>
                    <td>{n(row.target_1)?.toFixed(2) || "—"}</td>
                    <td>{n(row.risk_reward)?.toFixed(2) || "—"}</td>

                    <td>
                      {row.option
                        ? `${row.option.contract?.option_type || ""} ${
                            row.option.contract?.strike ?? ""
                          } · ${row.option.ltp ?? "—"}`
                        : "—"}
                    </td>

                    <td>
                      <span
                        className={`${styles.state} ${
                          row.risk_approved ? styles.good : styles.bad
                        }`}
                      >
                        {row.risk_action || "—"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!rows.length ? (
            <div className={styles.empty}>
              <strong>
                {data?.market_open === false
                  ? "Market is closed"
                  : "No live strategy setups"}
              </strong>
              <span>
                {data?.message ||
                  data?.last_error ||
                  "The scanner will populate when the realtime pipeline produces strategy setups."}
              </span>
            </div>
          ) : null}
        </section>
      </div>
    </Shell>
  );
}