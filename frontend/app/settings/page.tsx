"use client";

import { useEffect, useState } from "react";
import { Shell } from "../../components/Shell";
import styles from "./settings.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Preferences = {
  theme: "light" | "dark";
  refreshSeconds: number;
  compactTables: boolean;
  confirmPaperTrades: boolean;
  notifications: boolean;
};

const DEFAULTS: Preferences = {
  theme: "light",
  refreshSeconds: 5,
  compactTables: false,
  confirmPaperTrades: true,
  notifications: true,
};

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULTS);
  const [system, setSystem] = useState<any>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("trading-intelligence-settings");
      if (raw) setPrefs({ ...DEFAULTS, ...JSON.parse(raw) });
    } catch {
      // Defaults are safe.
    }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = prefs.theme;
    document.documentElement.dataset.compactTables = prefs.compactTables ? "true" : "false";
  }, [prefs.theme, prefs.compactTables]);

  async function loadSystem() {
    try {
      const response = await fetch(`${API}/ui/system-status`, { cache: "no-store" });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "System status failed.");
      setSystem(body);
      setError("");
    } catch (e: any) {
      setError(e?.message || "Backend unavailable.");
    }
  }

  useEffect(() => {
    loadSystem();
    const timer = window.setInterval(loadSystem, 10000);
    return () => clearInterval(timer);
  }, []);

  function save() {
    localStorage.setItem("trading-intelligence-settings", JSON.stringify(prefs));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2200);
  }

  function update<K extends keyof Preferences>(key: K, value: Preferences[K]) {
    setPrefs((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  return (
    <Shell>
      <div className={styles.page}>
        <header className={styles.header}>
          <div><div className={styles.eyebrow}>System</div><h1>Settings</h1><p>Browser preferences plus live backend/system visibility. Server secrets stay outside the UI.</p></div>
          <button className={styles.primary} onClick={save}>Save preferences</button>
        </header>

        {error ? <div className={styles.error}>{error}</div> : null}

        <div className={styles.grid}>
          <section className={styles.card}>
            <div className={styles.eyebrow}>Appearance</div><h2>Interface</h2>
            <label>Theme<select value={prefs.theme} onChange={(e) => update("theme", e.target.value as "light" | "dark")}><option value="light">Light</option><option value="dark">Dark</option></select></label>
            <label className={styles.switchRow}><span><b>Compact tables</b><small>Reduce dense table spacing across pages.</small></span><input type="checkbox" checked={prefs.compactTables} onChange={(e) => update("compactTables", e.target.checked)} /></label>
            <label className={styles.switchRow}><span><b>Notifications</b><small>Frontend notifications where supported.</small></span><input type="checkbox" checked={prefs.notifications} onChange={(e) => update("notifications", e.target.checked)} /></label>
          </section>

          <section className={styles.card}>
            <div className={styles.eyebrow}>Refresh</div><h2>Live polling</h2>
            <label>Default interval<select value={String(prefs.refreshSeconds)} onChange={(e) => update("refreshSeconds", Number(e.target.value))}><option value="5">5 sec</option><option value="10">10 sec</option><option value="15">15 sec</option><option value="30">30 sec</option><option value="60">60 sec</option></select></label>
            <div className={styles.info}><span>Selected</span><b>{prefs.refreshSeconds} seconds</b></div>
            <div className={styles.info}><span>Preference storage</span><b>Browser localStorage</b></div>
          </section>

          <section className={styles.card}>
            <div className={styles.eyebrow}>Paper safety</div><h2>Execution preference</h2>
            <label className={styles.switchRow}><span><b>Confirm paper trades</b><small>Keep confirmation enabled for manual simulated orders.</small></span><input type="checkbox" checked={prefs.confirmPaperTrades} onChange={(e) => update("confirmPaperTrades", e.target.checked)} /></label>
            <div className={styles.safety}><b>SIMULATION ONLY</b><span>Preferences cannot enable live broker execution.</span></div>
          </section>

          <section className={styles.card}>
            <div className={styles.eyebrow}>Backend</div><h2>System status</h2>
            <div className={styles.systemList}>
              <div><span>API</span><b className={system?.backend === "CONNECTED" ? styles.good : styles.bad}>{system?.backend || "CHECKING"}</b></div>
              <div><span>Realtime pipeline</span><b>{system?.realtime_pipeline?.running ? "RUNNING" : "STOPPED"}</b></div>
              <div><span>Cycle count</span><b>{system?.realtime_pipeline?.cycle_count ?? "—"}</b></div>
              <div><span>Last error</span><b>{system?.realtime_pipeline?.last_error || "None"}</b></div>
              <div><span>Risk config</span><b>{system?.risk_config?.loaded ? "LOADED" : "—"}</b></div>
              <div><span>Paper mode</span><b>{system?.paper?.mode || "—"}</b></div>
              <div><span>Live execution</span><b className={system?.paper?.live_execution === false ? styles.good : styles.bad}>{system?.paper?.live_execution === false ? "DISABLED" : "UNKNOWN"}</b></div>
              <div><span>Direct browser → Upstox</span><b className={system?.market_data_boundary?.browser_direct_upstox === false ? styles.good : styles.bad}>{system?.market_data_boundary?.browser_direct_upstox === false ? "BLOCKED" : "CHECK"}</b></div>
            </div>
          </section>
        </div>

        {saved ? <div className={styles.saved}>Preferences saved locally.</div> : null}
        <div className={styles.note}>Settings are split intentionally: user-interface preferences are local, while trading/risk/broker configuration remains backend-controlled.</div>
      </div>
    </Shell>
  );
}
