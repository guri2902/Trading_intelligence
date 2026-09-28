
from __future__ import annotations
import json, os, time, uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Sequence
import requests
try:
    import websocket
except Exception:
    websocket=None

UPSTOX_AUTHORIZE_URL="https://api.upstox.com/v3/feed/market-data-feed/authorize"

@dataclass
class LiveTick:
    instrument_key: str
    ltp: float|None=None; close: float|None=None
    bid: float|None=None; ask: float|None=None
    bid_qty: int|None=None; ask_qty: int|None=None
    volume: float|None=None; oi: float|None=None; iv: float|None=None
    delta: float|None=None; gamma: float|None=None; theta: float|None=None
    vega: float|None=None; rho: float|None=None
    exchange_ts_ms: int|None=None; received_ts_ms: int|None=None
    status: str="OK"; source: str="upstox_v3"

@dataclass
class LiveFeedState:
    connected: bool=False; authenticated: bool=False
    subscribed:list[str]=field(default_factory=list)
    last_market_ts_ms:int|None=None; last_received_ts_ms:int|None=None
    segment_status:Dict[str,str]=field(default_factory=dict)
    message_count:int=0; error_count:int=0; last_error:str=""

class UpstoxLiveFeed:
    def __init__(self, access_token: str|None=None, authorize_url: str=UPSTOX_AUTHORIZE_URL, timeout:float=15.0):
        self.access_token=access_token or os.getenv("UPSTOX_ACCESS_TOKEN")
        self.authorize_url=authorize_url; self.timeout=timeout
        self.state=LiveFeedState(); self._ws=None

    def authorize(self)->str:
        if not self.access_token: raise RuntimeError("UPSTOX_ACCESS_TOKEN is not configured")
        r=requests.get(self.authorize_url,headers={"Authorization":f"Bearer {self.access_token}","Accept":"*/*"},timeout=self.timeout)
        r.raise_for_status(); p=r.json()
        uri=(p.get("data") or {}).get("authorized_redirect_uri") or p.get("authorized_redirect_uri")
        if not uri: raise RuntimeError("Upstox authorize response did not contain authorized websocket URI")
        return str(uri)

    def connect(self, instrument_keys:Sequence[str], mode:str="full", *, on_tick:Optional[Callable[[LiveTick],None]]=None)->None:
        if not instrument_keys: raise ValueError("at least one instrument key is required")
        if mode not in {"ltpc","option_greeks","full","full_d30"}: raise ValueError("unsupported Upstox V3 mode")
        if websocket is None: raise RuntimeError("websocket-client is required for live feed")
        url=self.authorize()
        self._ws=websocket.create_connection(url,header=[f"Authorization: Bearer {self.access_token}","Accept: */*"],timeout=self.timeout)
        self.state.connected=True; self.state.authenticated=True
        self.state.subscribed=list(dict.fromkeys(instrument_keys))
        req={"guid":uuid.uuid4().hex,"method":"sub","data":{"mode":mode,"instrumentKeys":self.state.subscribed}}
        self._ws.send_binary(json.dumps(req).encode())
        while True:
            msg=self._ws.recv()
            if msg is None: break
            try:
                decoded=json.loads(msg if isinstance(msg,str) else msg.decode())
            except Exception:
                self.state.error_count+=1; self.state.last_error="protobuf decoder not configured"; continue
            self.state.message_count+=1
            for tick in self.decode_json(decoded):
                self.state.last_market_ts_ms=tick.exchange_ts_ms or self.state.last_market_ts_ms
                self.state.last_received_ts_ms=tick.received_ts_ms or self.state.last_received_ts_ms
                if on_tick: on_tick(tick)

    def close(self)->None:
        try:
            if self._ws is not None: self._ws.close()
        finally:
            self._ws=None; self.state.connected=False; self.state.authenticated=False; self.state.subscribed=[]

    def decode_json(self,payload:dict[str,Any])->list[LiveTick]:
        now=int(time.time()*1000)
        if payload.get("type")=="market_info":
            m=payload.get("marketInfo") or {}; self.state.segment_status=dict(m.get("segmentStatus") or {})
            if payload.get("currentTs") is not None: self.state.last_market_ts_ms=int(payload["currentTs"])
            return []
        if payload.get("type")!="live_feed": return []
        out=[]; current=int(payload.get("currentTs",now))
        for key,raw in (payload.get("feeds") or {}).items():
            raw=raw or {}
            if "fullFeed" in raw:
                ff=raw["fullFeed"]; marketff=ff.get("marketFF") or {}
                first=marketff
                depth=(marketff.get("marketLevel") or {}).get("bidAskQuote") or []
                greeks=marketff.get("optionGreeks") or {}
            elif "firstLevelWithGreeks" in raw:
                first=raw["firstLevelWithGreeks"]; depth=[]
                greeks=first.get("optionGreeks") or {}
            else:
                first=raw; depth=[]; greeks=first.get("optionGreeks") or {}
            ltpc=first.get("ltpc") or {}
            fd=first.get("firstDepth") or (depth[0] if depth else {})
            out.append(LiveTick(
                instrument_key=key, ltp=self._f(ltpc.get("ltp")), close=self._f(ltpc.get("cp")),
                bid=self._f(fd.get("bidP")), ask=self._f(fd.get("askP")),
                bid_qty=self._i(fd.get("bidQ")), ask_qty=self._i(fd.get("askQ")),
                volume=self._f(first.get("vtt")), oi=self._f(first.get("oi")), iv=self._f(first.get("iv")),
                delta=self._f(greeks.get("delta")), gamma=self._f(greeks.get("gamma")),
                theta=self._f(greeks.get("theta")), vega=self._f(greeks.get("vega")), rho=self._f(greeks.get("rho")),
                exchange_ts_ms=self._i(ltpc.get("ltt")) or current, received_ts_ms=now))
        return out

    @staticmethod
    def _f(v): 
        try:return None if v is None else float(v)
        except:return None
    @staticmethod
    def _i(v):
        try:return None if v is None else int(v)
        except:return None

def freshness_ok(tick:LiveTick,max_age_ms:int=5000,now_ms:int|None=None)->bool:
    if tick.status!="OK" or tick.received_ts_ms is None:return False
    now=now_ms if now_ms is not None else int(time.time()*1000)
    return 0 <= now-tick.received_ts_ms <= max_age_ms

def quote_ok(tick:LiveTick)->bool:
    if tick.ltp is not None and tick.ltp < 0:return False
    if tick.bid is not None and tick.ask is not None and (tick.bid<0 or tick.ask<0 or tick.bid>tick.ask):return False
    return True
