"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function useLiveState(interval = 5000) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const response = await fetch(`${API_BASE}/pipeline/status`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`API ${response.status}`);
      }

      const payload = await response.json();

      setData(payload);
      setError("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Backend unavailable"
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();

    const timer = setInterval(refresh, interval);

    return () => clearInterval(timer);
  }, [interval]);

  return {
    data,
    loading,
    error,
  };
}