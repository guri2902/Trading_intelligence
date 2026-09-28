"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Shell } from "../../components/Shell";
import styles from "./option-chain.module.css";

type Quote = {
  instrument_key?: string;
  underlying_key?: string;
  expiry?: string;
  strike?: number | string;
  option_type?: string;
  optionType?: string;
  ltp?: number | null;
  bid?: number | null;
  ask?: number | null;
  volume?: number | null;
  open_interest?: number | null;
  change_in_oi?: number | null;
  iv?: number | null;
  delta?: number | null;
};

type ApiResponse = {
  status?: string;
  provider?: string;
  underlying?: string;
  underlying_key?: string;
  expiry?: string | null;
  available_expiries?: string[];
  snapshot_timestamp?: string | null;
  spot?: number | null;
  underlying_ltp?: number | null;
  quotes?: Quote[];
  contract_count?: number;
  source?: string;
  reason?: string | null;
};

const API =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

const UNDERLYINGS = [
  ["NIFTY", "NSE_INDEX|Nifty 50"],
  ["BANKNIFTY", "NSE_INDEX|Nifty Bank"],
  ["FINNIFTY", "NSE_INDEX|Nifty Fin Service"],
  ["SENSEX", "BSE_INDEX|SENSEX"],
] as const;

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function fmt(value: unknown, digits = 2): string {
  const n = toNumber(value);
  if (n === null) return "—";
  return n.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function compact(value: unknown): string {
  const n = toNumber(value);
  if (n === null) return "—";
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("en-IN");
}

export default function OptionChainPage() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [expiry, setExpiry] = useState("");
  const [windowSize, setWindowSize] = useState(10);
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const underlyingKey =
    UNDERLYINGS.find(([name]) => name === symbol)?.[1] ||
    UNDERLYINGS[0][1];

  const load = useCallback(async () => {
    setError("");

    try {
      const params = new URLSearchParams({
        underlying: symbol,
        underlying_key: underlyingKey,
      });

      if (expiry) {
        params.set("expiry_date", expiry);
      }

      const response = await fetch(
        `${API}/ui/option-chain?${params.toString()}`,
        { cache: "no-store" },
      );

      const body = (await response.json()) as ApiResponse;

      if (!response.ok) {
        throw new Error(
          (body as { reason?: string; message?: string })?.reason ||
            (body as { reason?: string; message?: string })?.message ||
            `HTTP ${response.status}`,
        );
      }

      setData(body);
    } catch (cause) {
      setData(null);
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to load option-chain data.",
      );
    } finally {
      setLoading(false);
    }
  }, [expiry, underlyingKey]);

  useEffect(() => {
    setExpiry("");
  }, [symbol]);

  useEffect(() => {
    setLoading(true);
    void load();

    // Five-second polling is intentional: outside market hours the same
    // latest Upstox snapshot can be returned without inventing new prices.
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  const expiries = data?.available_expiries || [];

  useEffect(() => {
    if (!expiry && expiries.length > 0) {
      setExpiry(expiries[0]);
    }
  }, [expiry, expiries]);

  const spot =
    toNumber(data?.spot) ?? toNumber(data?.underlying_ltp);

  const rows = useMemo(() => {
    const flatQuotes = data?.quotes || [];

    // Backward-compatible fallback for the existing /ui/option-chain
    // contract: older responses may expose grouped rows instead of quotes.
    const legacyRows = (data as ApiResponse & {
      rows?: Array<{
        strike?: number | string;
        ce?: Quote | null;
        pe?: Quote | null;
      }>;
    } | null)?.rows || [];

    const quotes: Quote[] =
      flatQuotes.length > 0
        ? flatQuotes
        : legacyRows.flatMap((row) => {
            const result: Quote[] = [];
            if (row.ce) result.push(row.ce);
            if (row.pe) result.push(row.pe);
            return result;
          });

    const grouped = new Map<
      number,
      { ce?: Quote; pe?: Quote }
    >();

    for (const quote of quotes) {
      const strike = toNumber(quote.strike);
      const side = String(
        quote.option_type ?? quote.optionType ?? "",
      ).toUpperCase();

      if (strike === null || (side !== "CE" && side !== "PE")) {
        continue;
      }

      const item = grouped.get(strike) || {};

      if (side === "CE") item.ce = quote;
      if (side === "PE") item.pe = quote;

      grouped.set(strike, item);
    }

    let result = [...grouped.entries()]
      .map(([strike, value]) => ({ strike, ...value }))
      .sort((a, b) => a.strike - b.strike);

    if (spot !== null && result.length) {
      const atmIndex = result.reduce(
        (best, row, index) =>
          Math.abs(row.strike - spot) <
          Math.abs(result[best].strike - spot)
            ? index
            : best,
        0,
      );

      result = result.slice(
        Math.max(0, atmIndex - windowSize),
        Math.min(result.length, atmIndex + windowSize + 1),
      );
    }

    return result;
  }, [data, spot, windowSize]);

  const atmStrike =
    spot !== null && rows.length
      ? rows.reduce((best, row) =>
          Math.abs(row.strike - spot) <
          Math.abs(best.strike - spot)
            ? row
            : best,
        ).strike
      : null;

  const status = String(data?.status || "WAIT").toUpperCase();

  return (
    <Shell>
      <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <div className={styles.eyebrow}>MARKET DATA</div>
          <h1>Option Chain</h1>
          <p>
            Live/latest option contracts and quotes directly from Upstox.
          </p>
        </div>

        <div className={styles.status}>
          <span
            className={`${styles.dot} ${
              status === "LIVE" || status === "OK" ? styles.live : ""
            }`}
          />
          {status}
        </div>
      </header>

      <section className={styles.controls}>
        <label>
          UNDERLYING
          <select
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
          >
            {UNDERLYINGS.map(([name]) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>

        <label>
          EXPIRY
          <select
            value={expiry}
            onChange={(event) => setExpiry(event.target.value)}
            disabled={!expiries.length}
          >
            {expiries.length ? (
              expiries.map((item) => (
                <option key={item}>{item}</option>
              ))
            ) : (
              <option value="">No expiry</option>
            )}
          </select>
        </label>

        <label>
          STRIKES AROUND ATM
          <select
            value={windowSize}
            onChange={(event) =>
              setWindowSize(Number(event.target.value))
            }
          >
            {[5, 10, 15, 20].map((size) => (
              <option key={size} value={size}>
                ±{size}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={() => {
            setLoading(true);
            void load();
          }}
        >
          Refresh
        </button>
      </section>

      {error ? (
        <div className={styles.error}>{error}</div>
      ) : null}

      {!error && data?.reason && !data?.quotes?.length ? (
        <div className={styles.wait}>
          <b>WAIT</b>
          <span>{data.reason}</span>
        </div>
      ) : null}

      <section className={styles.summary}>
        <div className={styles.card}>
          <span>UNDERLYING</span>
          <strong>{data?.underlying || symbol}</strong>
        </div>
        <div className={styles.card}>
          <span>SPOT</span>
          <strong>{fmt(spot)}</strong>
        </div>
        <div className={styles.card}>
          <span>EXPIRY</span>
          <strong>{data?.expiry || expiry || "—"}</strong>
        </div>
        <div className={styles.card}>
          <span>CONTRACTS</span>
          <strong>{data?.contract_count ?? data?.quotes?.length ?? 0}</strong>
        </div>
        <div className={styles.card}>
          <span>SOURCE</span>
          <strong>{data?.provider?.toUpperCase() || "UPSTOX"}</strong>
        </div>
      </section>

      <section className={styles.tableCard}>
        <div className={styles.tableTitle}>
          <div>
            <div className={styles.eyebrow}>LIVE / LATEST CHAIN</div>
            <h2>{symbol} Option Chain</h2>
          </div>
          <span>UPSTOX · 5s REFRESH</span>
        </div>

        {loading && !data ? (
          <div className={styles.empty}>
            Loading option-chain data…
          </div>
        ) : !rows.length ? (
          <div className={styles.empty}>
            {data?.reason ||
              "Upstox did not return usable option rows for the selected expiry."}
          </div>
        ) : (
          <div className={styles.scroll}>
            <table>
              <thead>
                <tr>
                  <th colSpan={6}>CALLS</th>
                  <th>STRIKE</th>
                  <th colSpan={6}>PUTS</th>
                </tr>
                <tr>
                  <th>VOL</th>
                  <th>Δ</th>
                  <th>IV</th>
                  <th>Δ OI</th>
                  <th>OI</th>
                  <th>LTP</th>
                  <th>STRIKE</th>
                  <th>LTP</th>
                  <th>OI</th>
                  <th>Δ OI</th>
                  <th>IV</th>
                  <th>Δ</th>
                  <th>VOL</th>
                </tr>
              </thead>

              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.strike}
                    className={
                      row.strike === atmStrike ? styles.atm : ""
                    }
                  >
                    <td>{compact(row.ce?.volume)}</td>
                    <td>{fmt(row.ce?.delta, 4)}</td>
                    <td>{fmt(row.ce?.iv)}</td>
                    <td
                      className={
                        (toNumber(row.ce?.change_in_oi) ?? 0) >= 0
                          ? styles.pos
                          : styles.neg
                      }
                    >
                      {compact(row.ce?.change_in_oi)}
                    </td>
                    <td>{compact(row.ce?.open_interest)}</td>
                    <td>{fmt(row.ce?.ltp)}</td>

                    <td className={styles.strike}>
                      {fmt(row.strike, 0)}
                      {row.strike === atmStrike ? (
                        <small>ATM</small>
                      ) : null}
                    </td>

                    <td>{fmt(row.pe?.ltp)}</td>
                    <td>{compact(row.pe?.open_interest)}</td>
                    <td
                      className={
                        (toNumber(row.pe?.change_in_oi) ?? 0) >= 0
                          ? styles.pos
                          : styles.neg
                      }
                    >
                      {compact(row.pe?.change_in_oi)}
                    </td>
                    <td>{fmt(row.pe?.iv)}</td>
                    <td>{fmt(row.pe?.delta, 4)}</td>
                    <td>{compact(row.pe?.volume)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      </main>
    </Shell>
  );
}