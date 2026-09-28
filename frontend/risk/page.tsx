"use client";

import { FormEvent, useEffect, useState } from "react";
import { Shell } from "../components/Shell";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Config = {
  capital: number;
  per_trade_risk: number;
  daily_risk_budget: number;
  weekly_risk_budget: number;
  monthly_risk_budget: number;
  max_concurrent_risk: number;
  max_open_positions: number;
  max_trades_per_day: number;
  max_drawdown_pct: number;
  square_off_time: string;
  lot_sizes: Record<string, number>;
};

const empty: Config = {
  capital: 100000,
  per_trade_risk: 1000,
  daily_risk_budget: 2000,
  weekly_risk_budget: 5000,
  monthly_risk_budget: 10000,
  max_concurrent_risk: 2000,
  max_open_positions: 1,
  max_trades_per_day: 5,
  max_drawdown_pct: 5,
  square_off_time: "15:20",
  lot_sizes: { NIFTY: 65, BANKNIFTY: 30, FINNIFTY: 60, SENSEX: 20 },
};

export default function Risk() {
  const [cfg, setCfg] = useState<Config>(empty);
  const [instrument, setInstrument] = useState("NIFTY");
  const [entry, setEntry] = useState(0);
  const [stop, setStop] = useState(0);
  const [calc, setCalc] = useState<any>(null);
  const [message, setMessage] = useState("");

  const load = async () => {
    const res = await fetch(`${API}/risk-config`, { cache: "no-store" });
    if (res.ok) setCfg(await res.json());
  };

  useEffect(() => { load(); }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API}/risk-config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    });
    setMessage(res.ok ? "Risk settings saved" : "Unable to save risk settings");
  };

  const calculate = async () => {
    const res = await fetch(`${API}/risk-config/calculate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instrument,
        entry_price: Number(entry),
        stop_loss: Number(stop),
      }),
    });
    setCalc(res.ok ? await res.json() : null);
  };

  const setNumber = (key: keyof Config, value: string) =>
    setCfg({ ...cfg, [key]: Number(value) });

  return (
    <Shell>
      <div className="eyebrow">Capital & risk</div>
      <h1>Risk</h1>

      <div className="grid cols2 section">
        <form className="card" onSubmit={save}>
          <h3>Account risk controls</h3>

          <label>Capital
            <input type="number" min="1" value={cfg.capital}
              onChange={e => setNumber("capital", e.target.value)} />
          </label>

          <label>Risk per trade
            <input type="number" min="0" value={cfg.per_trade_risk}
              onChange={e => setNumber("per_trade_risk", e.target.value)} />
          </label>

          <div className="grid cols2">
            <label>Daily risk budget
              <input type="number" min="0" value={cfg.daily_risk_budget}
                onChange={e => setNumber("daily_risk_budget", e.target.value)} />
            </label>
            <label>Weekly risk budget
              <input type="number" min="0" value={cfg.weekly_risk_budget}
                onChange={e => setNumber("weekly_risk_budget", e.target.value)} />
            </label>
          </div>

          <div className="grid cols2">
            <label>Monthly risk budget
              <input type="number" min="0" value={cfg.monthly_risk_budget}
                onChange={e => setNumber("monthly_risk_budget", e.target.value)} />
            </label>
            <label>Concurrent risk
              <input type="number" min="0" value={cfg.max_concurrent_risk}
                onChange={e => setNumber("max_concurrent_risk", e.target.value)} />
            </label>
          </div>

          <div className="grid cols2">
            <label>Max open positions
              <input type="number" min="1" value={cfg.max_open_positions}
                onChange={e => setNumber("max_open_positions", e.target.value)} />
            </label>
            <label>Max trades/day
              <input type="number" min="1" value={cfg.max_trades_per_day}
                onChange={e => setNumber("max_trades_per_day", e.target.value)} />
            </label>
          </div>

          <div className="grid cols2">
            <label>Max drawdown %
              <input type="number" min="0" max="100" step="0.1" value={cfg.max_drawdown_pct}
                onChange={e => setNumber("max_drawdown_pct", e.target.value)} />
            </label>
            <label>Square-off
              <input type="time" value={cfg.square_off_time}
                onChange={e => setCfg({...cfg, square_off_time:e.target.value})} />
            </label>
          </div>

          <h3 className="section">Lot sizes</h3>
          <div className="grid cols2">
            {Object.entries(cfg.lot_sizes).map(([name, size]) => (
              <label key={name}>{name}
                <input type="number" min="1" value={size}
                  onChange={e => setCfg({
                    ...cfg,
                    lot_sizes: {...cfg.lot_sizes, [name]: Number(e.target.value)}
                  })} />
              </label>
            ))}
          </div>

          <button className="btn" type="submit">Save risk settings</button>
          {message && <div className="small">{message}</div>}
        </form>

        <div className="card">
          <h3>Lot calculator</h3>

          <label>Instrument
            <select value={instrument} onChange={e => setInstrument(e.target.value)}>
              {Object.keys(cfg.lot_sizes).map(x => <option key={x}>{x}</option>)}
            </select>
          </label>

          <label>Entry premium
            <input type="number" step="0.05" value={entry}
              onChange={e => setEntry(Number(e.target.value))} />
          </label>

          <label>Stop loss
            <input type="number" step="0.05" value={stop}
              onChange={e => setStop(Number(e.target.value))} />
          </label>

          <button className="btn" onClick={calculate}>Calculate lots</button>

          {calc && (
            <div className="section">
              <div className="grid cols2">
                <div className="note"><b>Lot size</b><div className="big">{calc.lot_size}</div></div>
                <div className="note"><b>Max lots</b><div className="big">{calc.max_lots_by_risk}</div></div>
                <div className="note"><b>Quantity</b><div className="big">{calc.quantity}</div></div>
                <div className="note"><b>Risk / lot</b><div className="big">₹{calc.risk_per_lot.toFixed(2)}</div></div>
              </div>
              <div className="note section">
                <b>Effective risk budget</b>
                <div className="big">₹{calc.effective_risk_budget.toFixed(2)}</div>
                <div className="small">
                  Estimated trade risk ₹{calc.estimated_trade_risk.toFixed(2)} ·
                  Capital required ₹{calc.capital_required.toFixed(2)}
                </div>
              </div>
              <div className={`pill ${calc.eligible ? "good" : "neutral"}`}>
                {calc.eligible ? "ELIGIBLE" : "BLOCKED"}
              </div>
              {calc.reasons?.length > 0 && <div className="small">{calc.reasons.join(" · ")}</div>}
            </div>
          )}
        </div>
      </div>
    </Shell>
  );
}
