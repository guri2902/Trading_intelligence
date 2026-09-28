from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any

@dataclass(frozen=True)
class RegimeSnapshot:
    timestamp: str
    trend: str
    volatility: str
    regime: str
    close: float
    ema_fast: float | None
    ema_slow: float | None
    realized_vol: float | None

def _ts(v: Any) -> datetime:
    if isinstance(v, datetime): value=v
    else: value=datetime.fromisoformat(str(v).replace("Z","+00:00"))
    if value.tzinfo is None: return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def _ema(values:list[float], period:int)->float|None:
    if len(values)<period:return None
    a=2.0/(period+1.0); out=values[0]
    for x in values[1:]: out=a*x+(1-a)*out
    return out

def _rolling_vol(closes:list[float], period:int=20)->float|None:
    if len(closes)<period+1:return None
    w=closes[-period-1:]
    rs=[w[i]/w[i-1]-1.0 for i in range(1,len(w))]
    if not rs:return None
    m=sum(rs)/len(rs)
    return (sum((x-m)**2 for x in rs)/len(rs))**0.5

def classify_history(rows:list[dict[str,Any]])->list[RegimeSnapshot]:
    rows=sorted(rows,key=lambda r:_ts(r["timestamp"])); closes=[]; raw=[]; out=[]
    for row in rows:
        c=float(row["close"]); closes.append(c); rv=_rolling_vol(closes)
        if rv is not None: raw.append(rv)
        fast=_ema(closes[-20:],20) if len(closes)>=5 else None
        slow=_ema(closes[-50:],50) if len(closes)>=10 else None
        if fast is None or slow is None: trend="NEUTRAL"
        elif fast>slow*1.0005: trend="UPTREND"
        elif fast<slow*0.9995: trend="DOWNTREND"
        else: trend="RANGE"
        if rv is None or len(raw)<10: vol="NORMAL"
        else:
            med=median(raw); vol="HIGH_VOL" if rv>=med*1.25 else ("LOW_VOL" if rv<=med*0.75 else "NORMAL")
        out.append(RegimeSnapshot(_ts(row["timestamp"]).isoformat(),trend,vol,f"{trend}_{vol}",c,fast,slow,rv))
    return out

def analyze_trade_history(underlying_rows:list[dict[str,Any]], trades:list[dict[str,Any]])->dict[str,Any]:
    snaps=classify_history(underlying_rows); times=[_ts(s.timestamp) for s in snaps]; grouped=defaultdict(list)
    for trade in trades:
        if trade.get("entry_time") is None or trade.get("net_pnl") is None: continue
        idx=bisect_right(times,_ts(trade["entry_time"]))-1
        if idx>=0: grouped[snaps[idx].regime].append(trade)
    results={}
    for name, ts in sorted(grouped.items()):
        pnls=[float(t["net_pnl"]) for t in ts]; wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<0]; gp=sum(wins); gl=abs(sum(losses))
        results[name]={"trades":len(pnls),"net_profit":sum(pnls),"win_rate_pct":len(wins)/len(pnls)*100.0 if pnls else 0.0,"profit_factor":gp/gl if gl>0 else None,"average_trade":sum(pnls)/len(pnls) if pnls else 0.0}
    total=sum(v["trades"] for v in results.values()); best=max(results.items(),key=lambda kv:kv[1]["net_profit"],default=None)
    return {"regimes":results,"trade_count_classified":total,"best_regime":best[0] if best else None,"regime_coverage_pct":total/len(trades)*100.0 if trades else 0.0,"lookahead_safe":True}
