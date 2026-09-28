from datetime import datetime, timezone, timedelta
from backend.app.options_backtest.models import HistoricalOptionBar
from backend.app.options_backtest.phase22_engine import MultiLegOptionsBacktestEngine

def b(t,ck,strike,ot,px,underlying,exp='2026-09-11'):
 return HistoricalOptionBar(timestamp=t,contract_key=ck,underlying_symbol='NIFTY',expiry=exp,strike=strike,option_type=ot,open=px,high=px+1,low=max(.1,px-1),close=px,underlying_close=underlying)

def test_two_leg_spread_and_expiry_settlement():
 t0=datetime(2026,9,10,10,tzinfo=timezone.utc); rows=[b(t0,'C1',25000,'CE',100,25080),b(t0,'P1',25000,'PE',100,25080),b(t0+timedelta(minutes=5),'C1',25000,'CE',120,25080),b(t0+timedelta(minutes=5),'P1',25000,'PE',80,25080),b(t0+timedelta(days=1),'C1',25000,'CE',100,25050,exp='2026-09-11'),b(t0+timedelta(days=1),'P1',25000,'PE',50,25050,exp='2026-09-11')]
 r=MultiLegOptionsBacktestEngine().run(rows,lambda c:{'legs':[{'contract_key':'C1','side':'BUY','quantity':1},{'contract_key':'P1','side':'SELL','quantity':1}]},strategy_name='SPREAD')
 assert r.trades and r.trades[0].exit_reason=='EXPIRY'
 assert len(r.settlements)==2

def test_missing_underlying_at_expiry_warns():
 t0=datetime(2026,9,10,10,tzinfo=timezone.utc); rows=[HistoricalOptionBar(timestamp=t0,contract_key='C1',underlying_symbol='NIFTY',expiry='2026-09-11',strike=25000,option_type='CE',open=100,high=101,low=99,close=100),HistoricalOptionBar(timestamp=datetime(2026,9,11,10,tzinfo=timezone.utc),contract_key='C1',underlying_symbol='NIFTY',expiry='2026-09-11',strike=25000,option_type='CE',open=120,high=121,low=119,close=120)]
 r=MultiLegOptionsBacktestEngine().run(rows,lambda c:{'legs':[{'contract_key':'C1','side':'BUY','quantity':1}]},strategy_name='TEST')
 assert any('MISSING_UNDERLYING_AT_EXPIRY' in w for w in r.warnings)
