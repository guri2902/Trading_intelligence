from datetime import datetime, timedelta, timezone
from backend.app.features.indicators import ema, rsi, vwap
from backend.app.features.engine import FeatureEngine
from backend.app.features.multitimeframe import build_multitimeframe_snapshot

def test_ema():
    assert ema([1,2,3,4,5],3)[2]==2.0

def test_rsi_uptrend():
    assert rsi([100,101,102,103,104,105],3)[-1]==100.0

def test_vwap_session_reset():
    x=vwap([11,12,21,22],[9,10,19,20],[10,11,20,21],[10,10,10,10],["A","A","B","B"])
    assert round(x[1],6)==10.5 and round(x[3],6)==20.5

def test_feature_engine():
    start=datetime(2026,9,7,9,15,tzinfo=timezone.utc)
    rows=[]
    for i in range(80):
        p=100+i*.2
        rows.append({"timestamp":start+timedelta(minutes=i),"open":p,
                     "high":p+1.5,"low":p-.5,"close":p+1,"volume":1000+(i%10)*100})
    f=FeatureEngine().calculate(rows)
    assert f["ema_alignment"]=="BULLISH"
    for k in ("ema_9","ema_20","ema_50","rsi_14","atr_14","vwap","relative_volume_20",
              "volatility_20","pdh","pdl","pdc","day_open","day_high","day_low"):
        assert k in f

def test_multitimeframe():
    x=build_multitimeframe_snapshot({
        "5m":{"ema_alignment":"BULLISH"},"15m":{"ema_alignment":"BULLISH"},
        "30m":{"ema_alignment":"BULLISH"},"1h":{"ema_alignment":"BULLISH"}})
    assert x["trend_alignment"]=="STRONG_BULLISH"
