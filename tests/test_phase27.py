
from backend.app.live.upstox_feed import UpstoxLiveFeed,freshness_ok,quote_ok
def test_ltcp():
 f=UpstoxLiveFeed(access_token="x"); t=f.decode_json({"type":"live_feed","currentTs":"1000","feeds":{"k":{"ltpc":{"ltp":100.5,"cp":90,"ltt":"999"}}}})[0]
 assert t.ltp==100.5 and t.exchange_ts_ms==999
def test_full():
 f=UpstoxLiveFeed(access_token="x")
 p={"type":"live_feed","currentTs":"1000","feeds":{"k":{"fullFeed":{"marketFF":{"ltpc":{"ltp":200,"cp":190,"ltt":"1000"},"marketLevel":{"bidAskQuote":[{"bidP":199.5,"bidQ":"75","askP":200.5,"askQ":"150"}]},"optionGreeks":{"delta":.5,"gamma":.01,"theta":-2,"vega":10,"rho":1},"vtt":"5000","oi":100000,"iv":.15}}}}}
 t=f.decode_json(p)[0]
 assert (t.bid,t.ask,t.bid_qty,t.delta,t.volume)==(199.5,200.5,75,.5,5000)
def test_market_info():
 f=UpstoxLiveFeed(access_token="x"); assert f.decode_json({"type":"market_info","currentTs":"123","marketInfo":{"segmentStatus":{"NSE_FO":"NORMAL_OPEN"}}})==[]; assert f.state.segment_status["NSE_FO"]=="NORMAL_OPEN"
def test_crossed_quote():
 f=UpstoxLiveFeed(access_token="x"); t=f.decode_json({"type":"live_feed","currentTs":"1","feeds":{"k":{"firstLevelWithGreeks":{"ltpc":{"ltp":10},"firstDepth":{"bidP":11,"askP":10}}}}})[0]; assert not quote_ok(t)
def test_freshness():
 f=UpstoxLiveFeed(access_token="x"); t=f.decode_json({"type":"live_feed","currentTs":"1","feeds":{"k":{"ltpc":{"ltp":10}}}})[0]; assert freshness_ok(t,1000,(t.received_ts_ms or 0)+500); assert not freshness_ok(t,1000,(t.received_ts_ms or 0)+1500)
def test_no_credential_needed_to_import():
 f=UpstoxLiveFeed(access_token=None); assert isinstance(f,UpstoxLiveFeed)
