from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.db.models import Base
from backend.app.paper.engine import PaperTradingEngine
from backend.app.paper.models import PaperCloseRequest, PaperMarkRequest, PaperOrderRequest

def db():
    e=create_engine("sqlite:///:memory:"); Base.metadata.create_all(e); return sessionmaker(bind=e)()

def test_open_mark_target_close():
    d=db(); e=PaperTradingEngine(); e.ensure_account(d,"a",50000)
    p=e.open(d,PaperOrderRequest(account_id="a",symbol="NIFTYCE",action="BUY_CE",option_type="CE",strike=25000,expiry="2026-09-17",quantity=50,entry_price=100,stop_loss=90,target_1=110,target_2=120,timestamp=datetime.now(timezone.utc)))
    marked=e.mark(d,PaperMarkRequest(account_id="a",instrument_key="NIFTYCE",price=111,timestamp=datetime.now(timezone.utc)))[0]
    assert marked.status=="CLOSED" and marked.realized_pnl > 0 and marked.total_costs > 0

def test_stop_loss_is_before_target():
    d=db(); e=PaperTradingEngine(); e.ensure_account(d,"a",50000)
    e.open(d,PaperOrderRequest(account_id="a",symbol="NIFTYCE",action="BUY_CE",option_type="CE",strike=25000,expiry="2026-09-17",quantity=50,entry_price=100,stop_loss=95,target_1=105,target_2=110,timestamp=datetime.now(timezone.utc)))
    p=e.mark(d,PaperMarkRequest(account_id="a",instrument_key="NIFTYCE",price=94,timestamp=datetime.now(timezone.utc)))[0]
    assert p.status=="CLOSED" and p.close_reason=="STOP_LOSS" and p.realized_pnl < 0 and p.total_costs > 0

def test_account_stats_persist():
    d=db(); e=PaperTradingEngine(); e.ensure_account(d,"a",50000)
    p=e.open(d,PaperOrderRequest(account_id="a",symbol="ABC",action="BUY_PE",option_type="PE",strike=100,expiry="2026-09-17",quantity=10,entry_price=20,stop_loss=18,target_1=22,timestamp=datetime.now(timezone.utc)))
    e.close(d,PaperCloseRequest(account_id="a",position_id=p.position_id,exit_price=22,timestamp=datetime.now(timezone.utc),reason="TARGET_1"))
    a=e.account(d,"a")
    assert a.total_trades==1 and a.open_positions==0 and a.realized_pnl < 0

def test_only_option_buys():
    d=db(); e=PaperTradingEngine(); e.ensure_account(d,"a",1000)
    try:
        e.open(d,PaperOrderRequest(account_id="a",symbol="ABC",action="SELL_CE",option_type="CE",strike=100,expiry="2026-09-17",quantity=1,entry_price=20,stop_loss=22,timestamp=datetime.now(timezone.utc)))
    except ValueError as ex:
        assert str(ex)=="PAPER_ONLY_BUY_OPTIONS"
    else: assert False
