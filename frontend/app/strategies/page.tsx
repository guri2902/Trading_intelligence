"use client";

import { useEffect, useMemo, useState } from "react";
import { Shell } from "../../components/Shell";
import styles from "./strategies.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Action = "BUY" | "SELL";
type OptionType = "CE" | "PE";
type StrikeMode = "ATM" | "ITM" | "OTM" | "SPECIFIC";
type ExpiryMode = "AUTO" | "NEAREST" | "SPECIFIC";
type ConditionLogic = "ALL" | "ANY";

type Leg = {
  action: Action;
  option_type: OptionType;
  expiry_mode: ExpiryMode;
  expiry: string;
  strike_mode: StrikeMode;
  strike: string;
  strike_offset: string;
  lots: number;
  price: string;
};

type Condition = {
  field: string;
  operator: string;
  value: string;
};

type StrategyForm = {
  name: string;
  description: string;
  instrument: string;
  timeframe: string;
  engine_strategy: string;
  direction: "AUTO" | "LONG" | "SHORT";
  condition_logic: ConditionLogic;
  option_action: "AUTO" | "BUY_CE" | "BUY_PE" | "NONE";
  expiry_mode: ExpiryMode;
  strike_mode: StrikeMode;
  strike_offset: number;
  stop_mode: "ATR" | "POINTS" | "PERCENT";
  stop_value: number;
  target_mode: "RR" | "POINTS" | "PERCENT" | "ATR";
  target_value: number;
  max_trades_per_day: number;
  entry_conditions: Condition[];
  exit_conditions: Condition[];
  legs: Leg[];
};

const engineCatalog = [
  ["VWAP Pullback", "VWAP_PULLBACK"],
  ["EMA Continuation", "EMA_CONTINUATION"],
  ["Opening Range Breakout", "ORB"],
  ["Opening Range Retest", "ORB_RETEST"],
  ["Support / Resistance Rejection", "SR_REJECTION"],
  ["Range Fade", "RANGE_FADE"],
  ["Momentum Continuation", "MOMENTUM_CONTINUATION"],
  ["Volatility Breakout", "VOLATILITY_BREAKOUT"],
  ["Option Directional", "OPTION_DIRECTIONAL"],
] as const;

const conditionFields = [
  "RSI14",
  "PRICE_VS_VWAP",
  "EMA_ALIGNMENT",
  "RELATIVE_VOLUME",
  "MOMENTUM",
  "VOLATILITY",
  "TREND",
  "REGIME",
  "BOS",
  "CHOCH",
];

const operators = ["GT", "GTE", "LT", "LTE", "EQ", "NE", "CROSSES_ABOVE", "CROSSES_BELOW"];

function blankLeg(): Leg {
  return {
    action: "BUY",
    option_type: "CE",
    expiry_mode: "NEAREST",
    expiry: "",
    strike_mode: "ATM",
    strike: "",
    strike_offset: "0",
    lots: 1,
    price: "",
  };
}

function blankForm(): StrategyForm {
  return {
    name: "",
    description: "",
    instrument: "NIFTY",
    timeframe: "5m",
    engine_strategy: "VWAP_PULLBACK",
        direction: "AUTO",
    condition_logic: "ALL",
    option_action: "AUTO",
    expiry_mode: "AUTO",
    strike_mode: "ATM",
    strike_offset: 0,
    stop_mode: "ATR",
    stop_value: 1,
    target_mode: "RR",
    target_value: 1.5,
    max_trades_per_day: 1,
    entry_conditions: [],
    exit_conditions: [],
    legs: [blankLeg()],
  };
}

function titleCase(value: string) {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function formatOffset(value: string | number) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "0";
  return numeric > 0 ? `+${numeric}` : `${numeric}`;
}

function strikeModeFromStored(
  optionType: OptionType,
  storedMode: string,
  storedSteps: number,
): StrikeMode {
  if (!storedSteps || storedMode === "ATM") return "ATM";

  if (storedMode === "ATM_PLUS") {
    return optionType === "CE" ? "OTM" : "ITM";
  }

  if (storedMode === "ATM_MINUS") {
    return optionType === "CE" ? "ITM" : "OTM";
  }

  return "ATM";
}

function visibleOffsetFromStored(
  optionType: OptionType,
  storedMode: string,
  storedSteps: number,
) {
  const magnitude = Math.abs(Number(storedSteps || 0)) * 50;

  if (!magnitude || storedMode === "ATM") return 0;

  if (storedMode === "ATM_PLUS") {
    return optionType === "CE" ? magnitude : -magnitude;
  }

  if (storedMode === "ATM_MINUS") {
    return optionType === "CE" ? -magnitude : magnitude;
  }

  return 0;
}

function offsetForMode(
  optionType: OptionType,
  mode: StrikeMode,
  currentOffset: string | number,
) {
  if (mode === "ATM" || mode === "SPECIFIC") return "0";

  const current = Number(currentOffset || 0);
  const magnitude = Math.max(Math.abs(Number.isFinite(current) ? current : 0), 50);

  // For calls: OTM is above spot and ITM is below spot.
  // For puts:  OTM is below spot and ITM is above spot.
  if (optionType === "CE") {
    return String(mode === "OTM" ? magnitude : -magnitude);
  }

  return String(mode === "OTM" ? -magnitude : magnitude);
}

function modeFromSignedOffset(
  optionType: OptionType,
  offset: number,
): StrikeMode {
  if (!offset) return "ATM";

  if (optionType === "CE") {
    return offset > 0 ? "OTM" : "ITM";
  }

  return offset < 0 ? "OTM" : "ITM";
}

function backendStrikeMode(
  optionType: OptionType,
  mode: StrikeMode,
  offset: number,
) {
  if (mode === "SPECIFIC" || !offset || mode === "ATM") {
    return "ATM";
  }

  if (optionType === "CE") {
    return offset > 0 ? "ATM_PLUS" : "ATM_MINUS";
  }

  return offset > 0 ? "ATM_PLUS" : "ATM_MINUS";
}

function icon(kind: "back" | "add" | "trash" | "copy" | "edit" | "chart") {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  if (kind === "add") return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>;
  if (kind === "trash") return <svg {...common}><path d="M5 7h14M9 7V5h6v2M8 10v7M12 10v7M16 10v7M7 7l1 14h8l1-14" /></svg>;
  if (kind === "copy") return <svg {...common}><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>;
  if (kind === "edit") return <svg {...common}><path d="m4 20 4-1 10-10a2 2 0 0 0-3-3L5 16l-1 4Z"/><path d="m13.5 6.5 4 4"/></svg>;
  if (kind === "chart") return <svg {...common}><path d="M4 19V5M4 19h16"/><path d="m7 15 3-4 3 2 5-7"/></svg>;
  return <svg {...common}><path d="M19 12H5M10 7l-5 5 5 5"/></svg>;
}

function payoffForLeg(leg: Leg, price: number, reference: number) {
  const strike =
    leg.strike_mode === "SPECIFIC"
      ? Number(leg.strike || reference)
      : reference + Number(leg.strike_offset || 0);

  const premium = Number(leg.price || 0);
  const intrinsic =
    leg.option_type === "CE"
      ? Math.max(price - strike, 0)
      : Math.max(strike - price, 0);

  const direction = leg.action === "BUY" ? 1 : -1;
  return direction * (intrinsic - premium) * Math.max(1, Number(leg.lots || 1));
}

function PayoffGraph({ legs, referenceSpot }: { legs: Leg[]; referenceSpot: number }) {
  if (!referenceSpot || referenceSpot <= 0) {
    return (
      <div className={styles.graphEmpty}>
        <strong>Payoff preview needs a reference spot</strong>
        <span>Enter a reference spot on the right to preview the structure.</span>
      </div>
    );
  }

  const prices = Array.from({ length: 61 }, (_, i) => referenceSpot * (0.88 + (i / 60) * 0.24));
  const values = prices.map((price) => legs.reduce((sum, leg) => sum + payoffForLeg(leg, price, referenceSpot), 0));
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = Math.max(max - min, 1);
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 100;
      const y = 88 - ((v - min) / span) * 76;
      return `${x},${y}`;
    })
    .join(" ");
  const zeroY = 88 - ((0 - min) / span) * 76;

  return (
    <div className={styles.graphWrap}>
      <div className={styles.graphMeta}>
        <span>Reference spot {referenceSpot.toFixed(2)}</span>
        <span>Preview only</span>
      </div>
      <svg className={styles.graph} viewBox="0 0 100 100" preserveAspectRatio="none">
        <rect x="0" y="0" width="100" height={zeroY} className={styles.graphProfit} />
        <rect x="0" y={zeroY} width="100" height={100 - zeroY} className={styles.graphLoss} />
        <line x1="0" y1={zeroY} x2="100" y2={zeroY} className={styles.graphAxis} vectorEffect="non-scaling-stroke" />
        <line x1="50" y1="0" x2="50" y2="100" className={styles.graphAxis} vectorEffect="non-scaling-stroke" />
        <polyline points={points} className={styles.graphLine} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className={styles.graphAxisLabels}>
        <span>{prices[0].toFixed(0)}</span>
        <span>{referenceSpot.toFixed(0)}</span>
        <span>{prices.at(-1)!.toFixed(0)}</span>
      </div>
    </div>
  );
}

export default function StrategiesPage() {
  const [tab, setTab] = useState<"builder" | "library">("builder");
  const [items, setItems] = useState<any[]>([]);
  const [form, setForm] = useState<StrategyForm>(blankForm);
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [libraryFilter, setLibraryFilter] = useState<"ALL" | "ACTIVE" | "DRAFT" | "DISABLED">("ALL");
  const [referenceSpot, setReferenceSpot] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const response = await fetch(`${API}/strategy-studio/strategies`, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Strategy library unavailable.");
      setItems(body.strategies || []);
      setError("");
    } catch (e: any) {
      setError(e?.message || "Strategy library unavailable.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
      const searchable = `${item.name || ""} ${item.engine_strategy || ""} ${item.instruments?.[0] || ""}`.toLowerCase();
      const matchesQuery = !q || searchable.includes(q);
      const matchesFilter = libraryFilter === "ALL" || item.status === libraryFilter;
      return matchesQuery && matchesFilter;
    });
  }, [items, query, libraryFilter]);

  function resetBuilder() {
    setEditing(null);
    setForm(blankForm());
    setMessage("");
    setError("");
  }

  function setLeg(index: number, patch: Partial<Leg>) {
    setForm((current) => {
      const legs = [...current.legs];
      legs[index] = { ...legs[index], ...patch };
      return { ...current, legs };
    });
  }

  function addLeg() {
    setForm((current) => ({ ...current, legs: [...current.legs, blankLeg()] }));
  }

  function removeLeg(index: number) {
    setForm((current) => ({
      ...current,
      legs: current.legs.length <= 1 ? [blankLeg()] : current.legs.filter((_, i) => i !== index),
    }));
  }

  function addCondition(kind: "entry_conditions" | "exit_conditions") {
    setForm((current) => ({
      ...current,
      [kind]: [...current[kind], { field: "RSI14", operator: "GT", value: "50" }],
    }));
  }

  function updateCondition(kind: "entry_conditions" | "exit_conditions", index: number, patch: Partial<Condition>) {
    setForm((current) => {
      const next = [...current[kind]];
      next[index] = { ...next[index], ...patch };
      return { ...current, [kind]: next };
    });
  }

  function removeCondition(kind: "entry_conditions" | "exit_conditions", index: number) {
    setForm((current) => ({
      ...current,
      [kind]: current[kind].filter((_, i) => i !== index),
    }));
  }

  function loadPreset(name: string) {
    const next = blankForm();
    next.name = name;

    if (name === "Bull Call Spread") {
      next.description = "Defined-risk bullish call spread.";
      next.direction = "LONG";
      next.option_action = "BUY_CE";
      next.legs = [
        { ...blankLeg(), action: "BUY", option_type: "CE", strike_mode: "ATM", price: "" },
        { ...blankLeg(), action: "SELL", option_type: "CE", strike_mode: "OTM", strike_offset: "50", price: "" },
      ];
    }

    if (name === "Bear Put Spread") {
      next.description = "Defined-risk bearish put spread.";
      next.direction = "SHORT";
      next.option_action = "BUY_PE";
      next.legs = [
        { ...blankLeg(), action: "BUY", option_type: "PE", strike_mode: "ATM", price: "" },
        { ...blankLeg(), action: "SELL", option_type: "PE", strike_mode: "OTM", strike_offset: "-50", price: "" },
      ];
    }

    if (name === "Long Straddle") {
      next.description = "Buy ATM call and put.";
      next.legs = [
        { ...blankLeg(), action: "BUY", option_type: "CE", price: "" },
        { ...blankLeg(), action: "BUY", option_type: "PE", price: "" },
      ];
    }

    if (name === "Short Straddle") {
      next.description = "Sell ATM call and put.";
      next.legs = [
        { ...blankLeg(), action: "SELL", option_type: "CE", price: "" },
        { ...blankLeg(), action: "SELL", option_type: "PE", price: "" },
      ];
    }

    setForm(next);
    setEditing(null);
    setMessage(`${name} loaded into the builder.`);
    setTab("builder");
  }

  function editStrategy(strategy: any) {
    const rules = strategy.rules || {};
    setEditing(strategy.id);
    setTab("builder");
    setMessage("");

    setForm({
      name: strategy.name || "",
      description: strategy.description || "",
      instrument: strategy.instruments?.[0] || "NIFTY",
      timeframe: strategy.timeframe || "5m",
      engine_strategy: strategy.engine_strategy || ((strategy.rules?.legs?.length || 0) > 0 ? "VWAP_PULLBACK" : ""),
      direction: rules.direction || "AUTO",
      condition_logic: rules.condition_logic || "ALL",
      option_action: rules.option_action || "AUTO",
      expiry_mode: rules.expiry_mode || "AUTO",
      strike_mode: rules.strike_mode || "ATM",
      strike_offset: Number(rules.strike_offset || 0),
      stop_mode: rules.stop_mode || "ATR",
      stop_value: Number(rules.stop_value || 1),
      target_mode: rules.target_mode || "RR",
      target_value: Number(rules.target_value || 1.5),
      max_trades_per_day: Number(rules.max_trades_per_day || 1),
      entry_conditions: (rules.entry_conditions || []).map((x: any) => ({
        field: String(x.field || "RSI14"),
        operator: String(x.operator || "GT"),
        value: String(x.value ?? ""),
      })),
      exit_conditions: (rules.exit_conditions || []).map((x: any) => ({
        field: String(x.field || "RSI14"),
        operator: String(x.operator || "LT"),
        value: String(x.value ?? ""),
      })),
      legs: (rules.legs?.length ? rules.legs : [blankLeg()]).map((x: any) => {
        const optionType = (x.option_type || "CE") as OptionType;
        const storedMode = String(x.strike_mode || "ATM");
        const storedSteps = Number(x.strike_offset || 0);

        return {
          ...blankLeg(),
          ...x,
          option_type: optionType,
          strike_mode: strikeModeFromStored(optionType, storedMode, storedSteps),
          strike: x.strike == null ? "" : String(x.strike),
          strike_offset: String(visibleOffsetFromStored(optionType, storedMode, storedSteps)),
          expiry: x.expiry || "",
          price: "",
        };
      }),
    });
  }

  async function save() {
    if (saving) return;

    setMessage("");
    setError("");

    const name = form.name.trim();
    if (!name) {
      setError("Give the strategy a name before saving.");
      return;
    }

    if (!form.legs.length) {
      setError("Add at least one option leg.");
      return;
    }

    setSaving(true);

    const payload = {
      name,
      description: form.description.trim(),
      source: "USER",
      instruments: [form.instrument],
      timeframe: form.timeframe,
      engine_strategy: form.engine_strategy || (form.legs.length ? "VWAP_PULLBACK" : null),
      rules: {
        condition_logic: form.condition_logic,
        direction: form.direction,
        option_action: form.option_action,
        expiry_mode: form.expiry_mode,
        strike_mode: form.strike_mode,
        strike_offset: Number(form.strike_offset),
        stop_mode: form.stop_mode,
        stop_value: Number(form.stop_value),
        target_mode: form.target_mode,
        target_value: Number(form.target_value),
        max_trades_per_day: Number(form.max_trades_per_day),
        entry_conditions: form.entry_conditions.filter((x) => x.field.trim()).map((x) => ({
          field: x.field,
          operator: x.operator,
          value: Number.isNaN(Number(x.value)) ? x.value : Number(x.value),
        })),
        exit_conditions: form.exit_conditions.filter((x) => x.field.trim()).map((x) => ({
          field: x.field,
          operator: x.operator,
          value: Number.isNaN(Number(x.value)) ? x.value : Number(x.value),
        })),
        legs: form.legs.map((x) => ({
          action: x.action,
          option_type: x.option_type,
          expiry_mode: x.expiry_mode,
          expiry: x.expiry || null,
          strike_mode: backendStrikeMode(
            x.option_type,
            x.strike_mode,
            Number(x.strike_offset || 0),
          ),
          strike: x.strike ? Number(x.strike) : null,
          strike_offset:
            x.strike_mode === "SPECIFIC" || !x.strike_offset
              ? 0
              : Math.round(
                  Math.abs(Number(x.strike_offset || 0)) / 50,
                ),
          lots: Math.max(1, Number(x.lots || 1)),
        })),
      },
    };

    try {
      const url = editing
        ? `${API}/strategy-studio/strategies/${editing}`
        : `${API}/strategy-studio/strategies`;

      const response = await fetch(url, {
        method: editing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const body = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail || body || "Unable to save strategy."));
      }

      setEditing(body.id);
      setMessage(editing ? "Strategy version saved." : "Strategy created and saved.");
      await load();
    } catch (e: any) {
      setError(e?.message || "Unable to save strategy.");
    } finally {
      setSaving(false);
    }
  }

  async function duplicate(id: string) {
    try {
      const response = await fetch(`${API}/strategy-studio/strategies/${id}/duplicate`, { method: "POST" });
      if (!response.ok) throw new Error("Duplicate failed.");
      await load();
    } catch (e: any) {
      setError(e?.message || "Duplicate failed.");
    }
  }

  async function toggle(id: string, active: boolean) {
    try {
      const response = await fetch(`${API}/strategy-studio/strategies/${id}/${active ? "disable" : "enable"}`, { method: "POST" });
      if (!response.ok) throw new Error("Status update failed.");
      await load();
    } catch (e: any) {
      setError(e?.message || "Status update failed.");
    }
  }

  return (
    <Shell>
      <div className={styles.page}>
        <header className={styles.header}>
          <div>
            <div className={styles.eyebrow}>Research · Strategy Studio</div>
            <h1>Option Strategy Builder</h1>
            <p>Build multi-leg option structures, define the trigger and risk rules, save them, then send the exact strategy to Backtest.</p>
          </div>
          <button className={styles.primaryButton} onClick={resetBuilder}>
            {icon("add")} New strategy
          </button>
        </header>

        <div className={styles.tabs}>
          <button className={tab === "builder" ? styles.tabActive : styles.tab} onClick={() => setTab("builder")}>Builder</button>
          <button className={tab === "library" ? styles.tabActive : styles.tab} onClick={() => setTab("library")}>Library <span>{items.length}</span></button>
        </div>

        {error ? <div className={styles.error}>{error}</div> : null}
        {message ? <div className={styles.message}>{message}</div> : null}

        {tab === "builder" ? (
          <div className={styles.builder}>
            <main className={styles.left}>
              <section className={styles.section}>
                <div className={styles.sectionHead}>
                  <div>
                    <div className={styles.eyebrow}>01 · Strategy</div>
                    <h2>Define the strategy</h2>
                  </div>
                  {editing ? <span className={styles.badge}>Editing saved strategy</span> : null}
                </div>

                <div className={styles.formGrid}>
                  <label>
                    Strategy name
                    <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. NIFTY Bull Call Breakout" />
                  </label>
                  <label>
                    Underlying
                    <select value={form.instrument} onChange={(e) => setForm({ ...form, instrument: e.target.value })}>
                      <option>NIFTY</option>
                      <option>BANKNIFTY</option>
                      <option>FINNIFTY</option>
                      <option>SENSEX</option>
                    </select>
                  </label>
                  <label>
                    Timeframe
                    <select value={form.timeframe} onChange={(e) => setForm({ ...form, timeframe: e.target.value })}>
                      <option>1m</option><option>3m</option><option>5m</option><option>15m</option><option>30m</option><option>1h</option>
                    </select>
                  </label>
                  <label>
                    Strategy engine
                    <select value={form.engine_strategy} onChange={(e) => setForm({ ...form, engine_strategy: e.target.value })}>
                                            {engineCatalog.map(([name, key]) => <option value={key} key={key}>{name}</option>)}
                    </select>
                  </label>
                  <label className={styles.full}>
                    Description
                    <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What market condition is this strategy designed to exploit?" />
                  </label>
                </div>
              </section>

              <section className={styles.section}>
                <div className={styles.sectionHead}>
                  <div>
                    <div className={styles.eyebrow}>02 · Structure</div>
                    <h2>Option legs</h2>
                  </div>
                  <button className={styles.secondaryButton} onClick={addLeg}>{icon("add")} Add leg</button>
                </div>

                <div className={styles.legs}>
                  {form.legs.map((leg, i) => (
                    <div
                      className={styles.leg}
                      key={i}
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "minmax(82px, 0.9fr) minmax(82px, 0.9fr) minmax(118px, 1.1fr) minmax(110px, 1fr) minmax(145px, 1.2fr) minmax(60px, 0.55fr) minmax(145px, 1.25fr) 42px",
                        gap: 10,
                        alignItems: "start",
                      }}
                    >
                      <label style={{ minWidth: 0 }}>
                        <span>Action</span>
                        <select
                          aria-label={`Leg ${i + 1} action`}
                          value={leg.action}
                          onChange={(e) => setLeg(i, { action: e.target.value as Action })}
                        >
                          <option>BUY</option>
                          <option>SELL</option>
                        </select>
                      </label>

                      <label style={{ minWidth: 0 }}>
                        <span>Option type</span>
                        <select
                          aria-label={`Leg ${i + 1} option type`}
                          value={leg.option_type}
                          onChange={(e) => setLeg(i, { option_type: e.target.value as OptionType })}
                        >
                          <option>CE</option>
                          <option>PE</option>
                        </select>
                      </label>

                      <label style={{ minWidth: 0 }}>
                        <span>Expiry mode</span>
                        <select
                          aria-label={`Leg ${i + 1} expiry mode`}
                          value={leg.expiry_mode}
                          onChange={(e) => setLeg(i, { expiry_mode: e.target.value as ExpiryMode })}
                        >
                          <option>AUTO</option>
                          <option>NEAREST</option>
                          <option>SPECIFIC</option>
                        </select>
                      </label>

                      <label style={{ minWidth: 0 }}>
                        <span>Strike mode</span>
                        <select
                          aria-label={`Leg ${i + 1} strike mode`}
                          value={leg.strike_mode}
                          onChange={(e) => {
                            const mode = e.target.value as StrikeMode;
                            setLeg(i, {
                              strike_mode: mode,
                              strike_offset: offsetForMode(
                                leg.option_type,
                                mode,
                                leg.strike_offset,
                              ),
                            });
                          }}
                        >
                          <option value="ATM">ATM</option>
                          <option value="ITM">ITM</option>
                          <option value="OTM">OTM</option>
                          <option value="SPECIFIC">SPECIFIC</option>
                        </select>
                      </label>

                      <label style={{ minWidth: 0 }}>
                        <span>Strike offset (points)</span>
                        <input
                          aria-label={`Leg ${i + 1} strike offset in points`}
                          type="text"
                          inputMode="decimal"
                          value={leg.strike_offset}
                          disabled={leg.strike_mode === "ATM" || leg.strike_mode === "SPECIFIC"}
                          placeholder={leg.strike_mode === "ATM" ? "0" : "+200 / -200"}
                          onChange={(e) => {
                            // Do not touch strike_mode while editing. This fixes the
                            // "50 disappears and dropdown jumps to ATM" problem.
                            setLeg(i, {
                              strike_offset: e.target.value,
                            });
                          }}
                          onBlur={() => {
                            const raw = String(leg.strike_offset ?? "").trim();
                            if (!raw || !Number.isFinite(Number(raw))) {
                              setLeg(i, { strike_offset: "0" });
                            }
                          }}
                        />
                        <small>
                          {leg.strike_mode === "ATM"
                            ? "ATM = 0"
                            : leg.strike_mode === "SPECIFIC"
                              ? "Use Specific strike below"
                              : "Type + or − points"}
                        </small>
                      </label>

                      <label style={{ minWidth: 0 }}>
                        <span>Lots</span>
                        <input
                          aria-label={`Leg ${i + 1} lots`}
                          type="number"
                          min="1"
                          value={leg.lots}
                          onChange={(e) =>
                            setLeg(i, { lots: Math.max(1, Number(e.target.value)) })
                          }
                        />
                      </label>

                      <label style={{ minWidth: 0 }}>
                        <span>Entry premium</span>
                        <input
                          aria-label={`Leg ${i + 1} entry premium`}
                          type="number"
                          min="0"
                          step="0.05"
                          value={leg.price}
                          onChange={(e) => setLeg(i, { price: e.target.value })}
                          placeholder="Optional"
                        />
                      </label>

                      <button
                        className={styles.iconButton}
                        title="Remove leg"
                        aria-label={`Remove leg ${i + 1}`}
                        onClick={() => removeLeg(i)}
                        style={{ marginTop: 22 }}
                      >
                        {icon("trash")}
                      </button>

                      {leg.strike_mode === "SPECIFIC" ? (
                        <label
                          className={styles.specificStrike}
                          style={{ gridColumn: "1 / -1" }}
                        >
                          <span>Specific strike</span>
                          <input
                            type="number"
                            value={leg.strike}
                            onChange={(e) => setLeg(i, { strike: e.target.value })}
                            placeholder="Enter strike"
                          />
                        </label>
                      ) : null}

                      {leg.expiry_mode === "SPECIFIC" ? (
                        <label
                          className={styles.specificExpiry}
                          style={{ gridColumn: "1 / -1" }}
                        >
                          <span>Specific expiry</span>
                          <input
                            type="date"
                            value={leg.expiry}
                            onChange={(e) => setLeg(i, { expiry: e.target.value })}
                          />
                        </label>
                      ) : null}
                    </div>
                  ))}
                </div>

                <div className={styles.templates}>
                  <span className={styles.templateLabel}>Start from a template</span>
                  <div className={styles.templateGrid}>
                    {["Bull Call Spread", "Bear Put Spread", "Long Straddle", "Short Straddle"].map((name) => (
                      <button key={name} className={styles.template} onClick={() => loadPreset(name)}>
                        <strong>{name}</strong>
                        <span>Load into builder</span>
                      </button>
                    ))}
                  </div>
                </div>
              </section>

              <section className={styles.section}>
                <div className={styles.sectionHead}>
                  <div>
                    <div className={styles.eyebrow}>03 · Trigger</div>
                    <h2>Entry & exit conditions</h2>
                  </div>
                  <select className={styles.logicSelect} value={form.condition_logic} onChange={(e) => setForm({ ...form, condition_logic: e.target.value as ConditionLogic })}>
                    <option value="ALL">ALL conditions</option>
                    <option value="ANY">ANY condition</option>
                  </select>
                </div>

                <div className={styles.conditionBlock}>
                  <div className={styles.conditionHead}><strong>Entry</strong><button className={styles.linkButton} onClick={() => addCondition("entry_conditions")}>{icon("add")} Add condition</button></div>
                  {!form.entry_conditions.length ? <div className={styles.emptyLine}>No entry conditions yet. Add one or leave the strategy engine to define the trigger.</div> : null}
                  {form.entry_conditions.map((condition, i) => (
                    <div className={styles.conditionRow} key={i}>
                      <select value={condition.field} onChange={(e) => updateCondition("entry_conditions", i, { field: e.target.value })}>
                        {conditionFields.map((field) => <option key={field}>{field}</option>)}
                      </select>
                      <select value={condition.operator} onChange={(e) => updateCondition("entry_conditions", i, { operator: e.target.value })}>
                        {operators.map((operator) => <option key={operator}>{operator}</option>)}
                      </select>
                      <input value={condition.value} onChange={(e) => updateCondition("entry_conditions", i, { value: e.target.value })} placeholder="Value" />
                      <button className={styles.iconButton} onClick={() => removeCondition("entry_conditions", i)}>{icon("trash")}</button>
                    </div>
                  ))}
                </div>

                <div className={styles.conditionBlock}>
                  <div className={styles.conditionHead}><strong>Exit</strong><button className={styles.linkButton} onClick={() => addCondition("exit_conditions")}>{icon("add")} Add condition</button></div>
                  {!form.exit_conditions.length ? <div className={styles.emptyLine}>No explicit exit condition. Risk controls below still apply.</div> : null}
                  {form.exit_conditions.map((condition, i) => (
                    <div className={styles.conditionRow} key={i}>
                      <select value={condition.field} onChange={(e) => updateCondition("exit_conditions", i, { field: e.target.value })}>
                        {conditionFields.map((field) => <option key={field}>{field}</option>)}
                      </select>
                      <select value={condition.operator} onChange={(e) => updateCondition("exit_conditions", i, { operator: e.target.value })}>
                        {operators.map((operator) => <option key={operator}>{operator}</option>)}
                      </select>
                      <input value={condition.value} onChange={(e) => updateCondition("exit_conditions", i, { value: e.target.value })} placeholder="Value" />
                      <button className={styles.iconButton} onClick={() => removeCondition("exit_conditions", i)}>{icon("trash")}</button>
                    </div>
                  ))}
                </div>
              </section>

              <section className={styles.section}>
                <div className={styles.eyebrow}>04 · Risk</div>
                <h2>Stops, targets & limits</h2>
                <div className={styles.formGrid}>
                  <label>
                    Direction
                    <select value={form.direction} onChange={(e) => setForm({ ...form, direction: e.target.value as any })}>
                      <option>AUTO</option><option>LONG</option><option>SHORT</option>
                    </select>
                  </label>
                  <label>
                    Stop mode
                    <select value={form.stop_mode} onChange={(e) => setForm({ ...form, stop_mode: e.target.value as any })}>
                      <option>ATR</option><option>POINTS</option><option>PERCENT</option>
                    </select>
                  </label>
                  <label>
                    Stop value
                    <input type="number" min="0.01" step="0.01" value={form.stop_value} onChange={(e) => setForm({ ...form, stop_value: Number(e.target.value) })} />
                  </label>
                  <label>
                    Target mode
                    <select value={form.target_mode} onChange={(e) => setForm({ ...form, target_mode: e.target.value as any })}>
                      <option>RR</option><option>POINTS</option><option>PERCENT</option><option>ATR</option>
                    </select>
                  </label>
                  <label>
                    Target value
                    <input type="number" min="0.01" step="0.1" value={form.target_value} onChange={(e) => setForm({ ...form, target_value: Number(e.target.value) })} />
                  </label>
                  <label>
                    Max trades / day
                    <input type="number" min="1" value={form.max_trades_per_day} onChange={(e) => setForm({ ...form, max_trades_per_day: Math.max(1, Number(e.target.value)) })} />
                  </label>
                </div>
              </section>
            </main>

            <aside className={styles.right}>
              <section className={styles.previewCard}>
                <div className={styles.eyebrow}>Live preview</div>
                <div className={styles.previewTitleRow}>
                  <div>
                    <h2>{form.name || "Untitled strategy"}</h2>
                    <span>{form.instrument} · {form.timeframe} · {form.legs.length} leg{form.legs.length === 1 ? "" : "s"}</span>
                  </div>
                  <span className={styles.badge}>DRAFT</span>
                </div>

                <div className={styles.spotBox}>
                  <label>Reference spot for payoff preview
                    <input type="number" value={referenceSpot} onChange={(e) => setReferenceSpot(e.target.value)} placeholder="e.g. 25000" />
                  </label>
                </div>

                <PayoffGraph legs={form.legs} referenceSpot={Number(referenceSpot)} />

                <div className={styles.legSummary}>
                  {form.legs.map((leg, i) => (
                    <div key={i} className={styles.legSummaryRow}>
                      <span className={leg.action === "BUY" ? styles.buy : styles.sell}>{leg.action}</span>
                      <strong>{leg.option_type}</strong>
                      <span>
                        {titleCase(leg.strike_mode)}
                        {leg.strike_mode !== "SPECIFIC" && leg.strike_offset
                          ? ` ${formatOffset(leg.strike_offset)}`
                          : ""}
                      </span>
                      <span>{leg.lots} lot</span>
                    </div>
                  ))}
                </div>

                <div className={styles.saveBox}>
                  <div>
                    <strong>{editing ? "Save new version" : "Create this strategy"}</strong>
                    <span>Saved through the Strategy Studio backend.</span>
                  </div>
                  <button className={styles.primaryButton} disabled={saving} onClick={save}>
                    {saving ? "Saving…" : editing ? "Save version" : "Create strategy"}
                  </button>
                </div>

                {editing ? (
                  <a className={styles.secondaryLink} href={`/backtest?strategy=${editing}`}>{icon("chart")} Open this strategy in Backtest</a>
                ) : null}
              </section>
            </aside>
          </div>
        ) : (
          <section>
            <div className={styles.libraryTop}>
              <div>
                <div className={styles.eyebrow}>Saved strategies</div>
                <h2>Strategy Library</h2>
                <p>Every saved strategy is a card, so the library stays scannable instead of becoming a long list.</p>
              </div>
              <div className={styles.libraryControls}>
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name or engine…" />
                <select value={libraryFilter} onChange={(e) => setLibraryFilter(e.target.value as any)}>
                  <option>ALL</option><option>ACTIVE</option><option>DRAFT</option><option>DISABLED</option>
                </select>
                <button className={styles.primaryButton} onClick={resetBuilder}>{icon("add")} New strategy</button>
              </div>
            </div>

            {filtered.length ? (
              <div className={styles.libraryGrid}>
                {filtered.map((strategy: any) => (
                  <article className={styles.strategyCard} key={strategy.id}>
                    <div className={styles.cardTop}>
                      <span className={`${styles.status} ${strategy.status === "ACTIVE" ? styles.statusGood : strategy.status === "DISABLED" ? styles.statusBad : styles.statusWarn}`}>{strategy.status}</span>
                      <span className={styles.version}>v{strategy.version}</span>
                    </div>

                    <div className={styles.cardEyebrow}>{strategy.instruments?.[0] || "NIFTY"} · {strategy.timeframe || "5m"}</div>
                    <h3>{strategy.name}</h3>
                    <div className={styles.engine}>{strategy.engine_strategy || "CUSTOM RULES"}</div>
                    <p>{strategy.description || "No description."}</p>

                    <div className={styles.chips}>
                      <span>{strategy.rules?.legs?.length || 0} legs</span>
                      <span>{strategy.rules?.entry_conditions?.length || 0} entry</span>
                      <span>{strategy.rules?.exit_conditions?.length || 0} exit</span>
                    </div>

                    <div className={styles.cardActions}>
                      <button className={styles.secondaryButton} onClick={() => editStrategy(strategy)}>{icon("edit")} Edit</button>
                      <a className={styles.secondaryButton} href={`/backtest?strategy=${strategy.id}`}>{icon("chart")} Backtest</a>
                      <button className={styles.iconButton} title="Duplicate" onClick={() => duplicate(strategy.id)}>{icon("copy")}</button>
                      <button className={styles.iconButton} title={strategy.status === "ACTIVE" ? "Disable" : "Enable"} onClick={() => toggle(strategy.id, strategy.status === "ACTIVE")}>
                        {strategy.status === "ACTIVE" ? "×" : "✓"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className={styles.emptyLibrary}>
                <h3>No strategies found</h3>
                <p>Create your first strategy from the Builder or clear the filters.</p>
                <button className={styles.primaryButton} onClick={resetBuilder}>{icon("add")} Build a strategy</button>
              </div>
            )}
          </section>
        )}
      </div>
    </Shell>
  );
}
