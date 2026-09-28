export type HistoricalBar = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  open_interest?: number | null;
};

export async function loadPersistedCandles(params?: {
  canonicalKey?: string;
  timeframe?: string;
  limit?: number;
  fromDate?: string;
  toDate?: string;
}): Promise<HistoricalBar[]> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const q = new URLSearchParams();
  q.set("canonical_key", params?.canonicalKey || "NSE_INDEX|Nifty 50");
  q.set("timeframe", params?.timeframe || "minutes:5");
  q.set("limit", String(params?.limit || 500));
  if (params?.fromDate) q.set("from_date", params.fromDate);
  if (params?.toDate) q.set("to_date", params.toDate);

  const res = await fetch(`${base}/backtest-data/candles?${q.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to load persisted candles (${res.status})`);
  const body = await res.json();
  return body.rows || [];
}
