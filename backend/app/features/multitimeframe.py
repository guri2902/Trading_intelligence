def build_multitimeframe_snapshot(feature_by_timeframe):
    align=[feature_by_timeframe.get(tf,{}).get("ema_alignment")
           for tf in ("5m","15m","30m","1h")]
    align=[x for x in align if x]
    if align and all(x=="BULLISH" for x in align): trend="STRONG_BULLISH"
    elif align and all(x=="BEARISH" for x in align): trend="STRONG_BEARISH"
    elif align.count("BULLISH") > align.count("BEARISH"): trend="BULLISH"
    elif align.count("BEARISH") > align.count("BULLISH"): trend="BEARISH"
    else: trend="MIXED"
    return {"timeframes":feature_by_timeframe,"trend_alignment":trend}
