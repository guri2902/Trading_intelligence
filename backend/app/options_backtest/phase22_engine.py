from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from .models import HistoricalOptionBar
from .phase22_models import MultiLegOptionsBacktestConfig, MultiLegOptionsBacktestResult, SpreadTradeRecord, OptionLeg, ExpirySettlement
from ..backtest.costs import transaction_cost
from ..backtest.models import CostConfig

class MultiLegOptionsBacktestEngine:
    def _validate(self, rows: list[HistoricalOptionBar], cfg: MultiLegOptionsBacktestConfig):
        if not rows: raise ValueError('NO_HISTORICAL_OPTION_DATA')
        if sorted(rows, key=lambda x:x.timestamp) != rows: raise ValueError('OPTION_DATA_MUST_BE_CHRONOLOGICALLY_SORTED')
        seen=set()
        for r in rows:
            k=(r.contract_key,r.timestamp)
            if k in seen: raise ValueError('DUPLICATE_OPTION_BAR')
            seen.add(k)
            if r.high < max(r.open,r.close) or r.low > min(r.open,r.close): raise ValueError('INVALID_OPTION_OHLC')
            if r.bid is not None and r.ask is not None and r.bid > r.ask: raise ValueError('BID_ASK_CROSSED')
            if not cfg.allow_expiry_mismatch and r.expiry and r.timestamp.date().isoformat() > r.expiry:
                raise ValueError('BAR_AFTER_CONTRACT_EXPIRY')
        return rows

    @staticmethod
    def _fill(r, side, slippage_bps):
        ref=(r.ask if side=='BUY' else r.bid) or r.open
        return ref*(1+slippage_bps/10000) if side=='BUY' else ref*(1-slippage_bps/10000)

    @staticmethod
    def _settlement(r):
        if r.underlying_close is None:
            return None
        intrinsic=max(r.underlying_close-r.strike,0.0) if r.option_type=='CE' else max(r.strike-r.underlying_close,0.0)
        return ExpirySettlement(contract_key=r.contract_key,timestamp=r.timestamp,expiry=r.expiry,strike=r.strike,option_type=r.option_type,underlying_close=r.underlying_close,settlement_price=intrinsic,intrinsic_value=intrinsic)

    def run(self, rows, signal_fn, *, strategy_name, config=None):
        cfg=config or MultiLegOptionsBacktestConfig(); self._validate(rows,cfg)
        by_time=defaultdict(list)
        series=defaultdict(list)
        for r in rows: by_time[r.timestamp].append(r); series[r.contract_key].append(r)
        times=sorted(by_time)
        warnings=[]; settlements=[]
        for contract, rs in series.items():
            last=rs[-1]
            if cfg.auto_expiry_exit and last.timestamp.date().isoformat() >= last.expiry:
                s=self._settlement(last)
                if s: settlements.append(s)
                elif last.timestamp.date().isoformat()==last.expiry: warnings.append(f'MISSING_UNDERLYING_AT_EXPIRY:{contract}')
        trades=[]; capital=cfg.initial_capital; open_trade=None; tid=0
        for i,t in enumerate(times[:-1]):
            if open_trade is not None: continue
            hist=[r for r in rows if r.timestamp<=t]
            sig=signal_fn({'timestamp':t,'history':hist,'chain':by_time[t]})
            if not sig: continue
            legs_raw=sig.get('legs')
            if not legs_raw: continue
            if len(legs_raw)>cfg.max_legs: warnings.append('MAX_LEGS_EXCEEDED'); continue
            chosen=[]
            for x in legs_raw:
                ck=x.get('contract_key'); side=x.get('side','BUY').upper(); qty=int(x.get('quantity',cfg.quantity))
                if side not in {'BUY','SELL'} or not ck or qty<=0: chosen=[]; warnings.append('INVALID_LEG'); break
                nb=None
                seen=0
                for tt in times[i+1:]:
                    match=[r for r in by_time[tt] if r.contract_key==ck]
                    if match:
                        seen+=1
                        if seen>=cfg.latency_bars: nb=match[0]; break
                if nb is None: chosen=[]; warnings.append(f'NO_EXECUTION_BAR:{ck}'); break
                chosen.append((OptionLeg(contract_key=ck,side=side,quantity=qty),nb))
            if not chosen: continue
            tid+=1; entry_time=max(r.timestamp for _,r in chosen); entry_value=0.0
            for leg,r in chosen:
                fill=self._fill(r,leg.side,cfg.slippage_bps); entry_value += fill*leg.quantity*(1 if leg.side=='BUY' else -1)
            open_trade=(tid,chosen,entry_time,entry_value)
            # deterministic exit: contract expiry settlement when available, otherwise last common timestamp
            expiry_target=min(r.expiry for _,r in chosen)
            exit_candidates=[]
            for leg,r in chosen:
                rs=series[leg.contract_key]
                exp=[z for z in rs if z.timestamp.date().isoformat()>=expiry_target]
                exit_candidates.append(exp[0] if exp else rs[-1])
            exit_t=max(r.timestamp for r in exit_candidates)
            exit_value=0.0
            for leg,r in chosen:
                settle=next((s for s in settlements if s.contract_key==leg.contract_key),None) if cfg.auto_expiry_exit and r.timestamp.date().isoformat()>=r.expiry else None
                price=settle.settlement_price if settle else self._fill(r,'SELL' if leg.side=='BUY' else 'BUY',cfg.slippage_bps)
                exit_value += price*leg.quantity*(1 if leg.side=='SELL' else -1)
            expiry_exit = any(any(z.timestamp.date().isoformat() >= z.expiry for z in series[leg.contract_key]) for leg, _ in chosen)
            gross=exit_value-entry_value; cost=transaction_cost(entry_value=abs(entry_value), exit_value=abs(exit_value), config=CostConfig(brokerage_per_order=cfg.brokerage_per_order,exchange_txn_rate=cfg.exchange_txn_rate,sebi_rate=cfg.sebi_rate,gst_rate=cfg.gst_rate,stamp_duty_rate=cfg.stamp_duty_rate,stt_rate=cfg.stt_sell_rate)); net=gross-cost; capital+=net
            trades.append(SpreadTradeRecord(trade_id=tid,entry_time=entry_time,exit_time=exit_t,legs=[a for a,_ in chosen],entry_value=round(entry_value,6),exit_value=round(exit_value,6),gross_pnl=round(gross,6),costs=round(cost,6),net_pnl=round(net,6),exit_reason='EXPIRY' if expiry_exit else 'END_OF_DATA'))
            open_trade=None
        wins=[t.net_pnl for t in trades if t.net_pnl>0]; losses=[t.net_pnl for t in trades if t.net_pnl<0]
        return MultiLegOptionsBacktestResult(strategy=strategy_name,trades=trades,settlements=settlements,metrics={'initial_capital':cfg.initial_capital,'final_equity':capital,'net_profit':sum(t.net_pnl for t in trades),'total_trades':len(trades),'win_rate_pct':len(wins)/len(trades)*100 if trades else 0.0,'profit_factor':sum(wins)/abs(sum(losses)) if losses else (None if not wins else float('inf'))},warnings=warnings)
