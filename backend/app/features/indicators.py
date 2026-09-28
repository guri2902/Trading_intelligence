from __future__ import annotations
from typing import Sequence
import math

def _v(x: Sequence[float]) -> list[float]:
    return [float(i) for i in x]

def sma(values: Sequence[float], period: int):
    values = _v(values)
    if period <= 0: raise ValueError("period must be > 0")
    out = [None] * len(values)
    roll = 0.0
    for i, x in enumerate(values):
        roll += x
        if i >= period: roll -= values[i-period]
        if i >= period-1: out[i] = roll / period
    return out

def ema(values: Sequence[float], period: int):
    values = _v(values)
    if period <= 0: raise ValueError("period must be > 0")
    out = [None] * len(values)
    if len(values) < period: return out
    alpha = 2.0/(period+1.0)
    prev = sum(values[:period])/period
    out[period-1] = prev
    for i in range(period, len(values)):
        prev = alpha*values[i] + (1-alpha)*prev
        out[i] = prev
    return out

def true_range(highs, lows, closes):
    h, l, c = _v(highs), _v(lows), _v(closes)
    if not (len(h)==len(l)==len(c)): raise ValueError("OHLC arrays must match")
    if not h: return []
    out = [h[0]-l[0]]
    for i in range(1, len(h)):
        out.append(max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])))
    return out

def atr(highs, lows, closes, period=14):
    return sma(true_range(highs, lows, closes), period)

def rsi(closes, period=14):
    c = _v(closes)
    out = [None] * len(c)
    if period <= 0: raise ValueError("period must be > 0")
    if len(c) <= period: return out
    gains=[]; losses=[]
    for i in range(1, len(c)):
        d=c[i]-c[i-1]
        gains.append(max(d,0.0)); losses.append(max(-d,0.0))
    ag=sum(gains[:period])/period
    al=sum(losses[:period])/period
    def rv(g,l): return 100.0 if l == 0 else 100.0 - 100.0/(1.0+g/l)
    out[period]=rv(ag,al)
    for i in range(period,len(gains)):
        ag=((ag*(period-1))+gains[i])/period
        al=((al*(period-1))+losses[i])/period
        out[i+1]=rv(ag,al)
    return out

def vwap(highs, lows, closes, volumes, session_ids=None):
    h,l,c,v = _v(highs),_v(lows),_v(closes),_v(volumes)
    if not (len(h)==len(l)==len(c)==len(v)): raise ValueError("HLCV arrays must match")
    if session_ids is not None and len(session_ids)!=len(c): raise ValueError("session_ids length mismatch")
    out=[None]*len(c); pv=0.0; vol=0.0; current=None
    for i in range(len(c)):
        sid=session_ids[i] if session_ids is not None else "DEFAULT"
        if sid != current: pv=0.0; vol=0.0; current=sid
        typical=(h[i]+l[i]+c[i])/3.0
        bar_volume=max(v[i],0.0); pv += typical*bar_volume; vol += bar_volume
        out[i] = pv/vol if vol else typical
    return out

def rolling_std(values, period):
    x=[None if v is None else float(v) for v in values]; out=[None]*len(x)
    for i in range(period-1,len(x)):
        w=x[i-period+1:i+1]
        if any(v is None for v in w):
            continue
        m=sum(w)/period
        out[i]=math.sqrt(sum((z-m)**2 for z in w)/period)
    return out

def returns(closes, period=1):
    c=_v(closes); out=[None]*len(c)
    for i in range(period,len(c)):
        out[i]=(c[i]/c[i-period]-1.0) if c[i-period] else None
    return out

def momentum(closes, period=10):
    c=_v(closes); out=[None]*len(c)
    for i in range(period,len(c)): out[i]=c[i]-c[i-period]
    return out

def relative_volume(volumes, period=20):
    v=_v(volumes); base=sma(v,period); out=[None]*len(v)
    for i,x in enumerate(v):
        if base[i] and base[i] > 0: out[i]=x/base[i]
    return out
