from datetime import datetime, timezone
from .indicators import atr, ema, momentum, relative_volume, returns, rolling_std, rsi, vwap
from .levels import current_day_levels, distance_from_level, percent_distance_from_level, previous_day_levels

class FeatureEngine:
    def __init__(self, ema_periods=(9,20,50), rsi_period=14, atr_period=14,
                 relative_volume_period=20, volatility_period=20, momentum_period=10):
        self.ema_periods=ema_periods
        self.rsi_period=rsi_period
        self.atr_period=atr_period
        self.relative_volume_period=relative_volume_period
        self.volatility_period=volatility_period
        self.momentum_period=momentum_period

    def calculate(self, rows, session_ids=None):
        if not rows: raise ValueError("FeatureEngine requires at least one candle")
        rows=list(rows)
        closes=[float(r["close"]) for r in rows]; highs=[float(r["high"]) for r in rows]
        lows=[float(r["low"]) for r in rows]; opens=[float(r["open"]) for r in rows]
        vols=[float(r.get("volume") or 0) for r in rows]
        out={"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(rows),
             "timestamp":rows[-1]["timestamp"],"price":closes[-1],"open":opens[-1],
             "high":highs[-1],"low":lows[-1]}
        ema_series={}
        for p in self.ema_periods:
            ema_series[p]=ema(closes,p); out[f"ema_{p}"]=ema_series[p][-1]
        rr1=returns(closes,1); rr5=returns(closes,5); rr15=returns(closes,15)
        atrs=atr(highs,lows,closes,self.atr_period)
        rsis=rsi(closes,self.rsi_period)
        vw=vwap(highs,lows,closes,vols,session_ids)
        rv=relative_volume(vols,self.relative_volume_period)
        vol=rolling_std(rr1,self.volatility_period)
        mom=momentum(closes,self.momentum_period)
        out.update({"rsi_14":rsis[-1],"atr_14":atrs[-1],"vwap":vw[-1],
                    "relative_volume_20":rv[-1],"return_1":rr1[-1],"return_5":rr5[-1],
                    "return_15":rr15[-1],"momentum_10":mom[-1],"volatility_20":vol[-1]})
        out["vwap_distance"]=distance_from_level(closes[-1],vw[-1])
        out["vwap_distance_pct"]=percent_distance_from_level(closes[-1],vw[-1])
        prev=previous_day_levels(rows); cur=current_day_levels(rows)
        day=rows[-1]["timestamp"].date().isoformat()
        out.update({"pdh":prev.get(day,{}).get("pdh"),"pdl":prev.get(day,{}).get("pdl"),
                    "pdc":prev.get(day,{}).get("pdc"),"day_open":cur.get(day,{}).get("open"),
                    "day_high":cur.get(day,{}).get("high"),"day_low":cur.get(day,{}).get("low")})
        out.update({"distance_pdh":distance_from_level(closes[-1],out["pdh"]),
                    "distance_pdl":distance_from_level(closes[-1],out["pdl"]),
                    "distance_pdc":distance_from_level(closes[-1],out["pdc"]),
                    "range":highs[-1]-lows[-1],
                    "body":abs(closes[-1]-opens[-1]),
                    "upper_wick":highs[-1]-max(opens[-1],closes[-1]),
                    "lower_wick":min(opens[-1],closes[-1])-lows[-1]})
        e9,e20,e50=out["ema_9"],out["ema_20"],out["ema_50"]
        out["ema_alignment"]="INSUFFICIENT_DATA" if None in (e9,e20,e50) else (
            "BULLISH" if e9>e20>e50 else "BEARISH" if e9<e20<e50 else "MIXED")
        out["price_vs_vwap"]="ABOVE" if vw[-1] is not None and closes[-1]>vw[-1] else (
            "BELOW" if vw[-1] is not None and closes[-1]<vw[-1] else "AT_VWAP")
        return out
