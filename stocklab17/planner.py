"""Cost-aware hypothetical risk tickets. No broker orders or promised returns."""
from __future__ import annotations
import math,argparse,hashlib
from pathlib import Path
from datetime import datetime, timezone
from .audit import read,write,stats,HORIZONS
from .calendar import parse_time,clock,expected_close,covered
from .hygiene import clean_bars
DEFAULTS={'equity':100000.,'available_cash':100000.,'risk_fraction':.005,'position_fraction':.20,
 'gross_fraction':.60,'portfolio_risk_fraction':.015,'sector_fraction':.40,
 'commission_rate':.001425,'min_commission':20.,'slippage':.001,'min_reward_risk':1.5,
 'holding_sessions':10,'max_positions':3,'lot_size':1,'risk_confirmed':False,'holdings':[]}

def validate_account(account):
    a={**DEFAULTS,**account}
    for k in DEFAULTS:
        if k in ('holdings','risk_confirmed'):continue
        if not isinstance(a[k],(int,float)) or not math.isfinite(a[k]):raise ValueError('Non-finite '+k)
    if a['equity']<=0 or a['available_cash']<0:raise ValueError('Invalid capital')
    for k in ('risk_fraction','position_fraction','gross_fraction','portfolio_risk_fraction','sector_fraction'):
        if not 0<a[k]<=1:raise ValueError('Invalid fraction '+k)
    if not 0<=a['commission_rate']<=.02 or not 0<=a['slippage']<=.1 or a['min_commission']<0:raise ValueError('Invalid costs')
    if not 0<a['min_reward_risk']<=10:raise ValueError('Invalid R/R')
    if a['holding_sessions']!=int(a['holding_sessions']) or not 1<=a['holding_sessions']<=60:raise ValueError('Invalid holding period')
    if a['lot_size'] not in (1,1000) or a['max_positions']!=int(a['max_positions']) or not 1<=a['max_positions']<=20:raise ValueError('Invalid lots or positions')
    for h in a['holdings']:
        if any(not isinstance(h.get(k),(int,float)) or not math.isfinite(h[k]) or h[k]<0 for k in ('market_value','planned_risk')):raise ValueError('Invalid holdings')
    return a

def tick(p,etf=False):
    if etf:return .01 if p<50 else .05
    return .01 if p<10 else .05 if p<50 else .1 if p<100 else .5 if p<500 else 1 if p<1000 else 5

def floor_tick(p,etf=False):return round(math.floor((p+1e-9)/tick(p,etf))*tick(p,etf),4)
def ceil_tick(p,etf=False):return round(math.ceil((p-1e-9)/tick(p,etf))*tick(p,etf),4)

def ledger(q,entry,exit_price,a,etf=False):
    if q<=0:return {'buy_cash':0,'sell_net':0,'pnl':0,'return_pct':0,'total_cost':0}
    buy=q*entry*(1+a['slippage']);sell=q*exit_price*(1-a['slippage']);tax=.001 if etf else .003
    bf=max(a['min_commission'],buy*a['commission_rate']);sf=max(a['min_commission'],sell*a['commission_rate']);st=sell*tax
    cost=buy+bf;net=sell-sf-st
    return {'buy_cash':round(cost,2),'sell_net':round(net,2),'pnl':round(net-cost,2),
        'return_pct':round((net/cost-1)*100,4),'total_cost':round(q*(exit_price-entry)-(net-cost),2)}

def size_position(entry,stop,target,account,etf=False,sector=''):
    a=validate_account(account)
    if not all(math.isfinite(x) for x in (entry,stop,target)) or not 0<stop<entry<target:return {'quantity':0,'reason':'停損 < 進場 < 目標 才能計算'}
    held=a['holdings'];used=sum(h['market_value'] for h in held);usedrisk=sum(h['planned_risk'] for h in held)
    usedsector=sum(h['market_value'] for h in held if h.get('sector')==sector)
    caps=[a['available_cash'],a['equity']*a['position_fraction'],a['equity']*a['gross_fraction']-used,a['equity']*a['sector_fraction']-usedsector]
    cash=max(0,min(caps));risk=max(0,min(a['equity']*a['risk_fraction'],a['equity']*a['portfolio_risk_fraction']-usedrisk));lot=a['lot_size']
    upper=int(cash/(entry*(1+a['slippage']))//lot)
    if len([h for h in held if h['market_value']>0])>=a['max_positions']:upper=0
    lo,hi=0,max(0,upper)
    while lo<hi:
        mid=(lo+hi+1)//2;test=ledger(mid*lot,entry,stop,a,etf)
        if test['buy_cash']<=cash+1e-8 and -test['pnl']<=risk+1e-8:lo=mid
        else:hi=mid-1
    q=lo*lot;loss=ledger(q,entry,stop,a,etf);win=ledger(q,entry,target,a,etf);flat=ledger(q,entry,entry,a,etf)
    return {'quantity':q,'cash_cap':round(cash,2),'risk_cap':round(risk,2),'buy_cash':loss['buy_cash'],
      'planned_stop_loss':round(-loss['pnl'],2),'net_reward_risk':round(win['pnl']/(-loss['pnl']),4) if loss['pnl']<0 else None,
      'stop_scenario':loss,'flat_scenario':flat,'target_scenario':win,
      'reason':'現金／部位／同業／總風險／交易單位取最嚴限制' if q else '資金、風險、持倉或交易單位限制使股數為0'}

def history_reference(records,stock,cutoff,h):
    at=parse_time(cutoff);label=stock.get('decision',{}).get('code');etf=stock['symbol'].startswith('00')
    eligible=[r for r in records if r.get('original_code')==label and r.get('etf')==etf and r.get(f'h{h}',{}).get('status')=='mature' and clock(r[f'h{h}']['exit_date'],13,30)<at]
    selected=[];until={}
    for r in sorted(eligible,key=lambda r:(r['entry_date'],r['symbol'])):
        if r['entry_date']<=until.get(r['symbol'],''):continue
        selected.append(r);until[r['symbol']]=r[f'h{h}']['exit_date']
    s=stats(selected,h);s['non_overlapping_per_symbol']=True;s['still_correlated']=True
    s['estimate_status']='exploratory_only' if s['n']>=30 and s['entry_dates']>=10 and s['symbols']>=5 else 'insufficient_diversity'
    s['strategy_match']=False;s['explanation']='舊標籤固定持有期參考，不是v17限價停損策略期望；未含最低手續費，仍有市場相關性'
    return s

def make_plan(stock,snapshot_at,account=None,records=None):
    a=validate_account(account or {});at=parse_time(snapshot_at);d=stock.get('decision',{});etf=stock['symbol'].startswith('00')
    rows,issues=clean_bars(stock.get('candles',[]),snapshot_at)
    from stocklab16.indicators import enrich
    rows=enrich([{k:r.get(k) for k in ('date','open','high','low','close','volume','corporate_action')} for r in rows]) if rows else []
    last=rows[-1] if rows else {};c=last.get('close');atr=last.get('atr');res=last.get('resistance');ma20=last.get('ma20');ma60=last.get('ma60')
    blocks=[];expected=expected_close(snapshot_at)
    if not covered(expected):blocks.append('交易日曆尚未核對此日期；先更新日曆，不自動下單')
    if last.get('date')!=expected:blocks.append(f'行情落後：應有 {expected} 完整日K，實際只有 {last.get("date","缺值")}')
    if d.get('code') in ('avoid','insufficient'):blocks.append('原判斷偏弱或資料不足，不能因有價格情境就升級買入')
    if etf:blocks.append('ETF曝險、折溢價、追蹤差異未驗證，不套個股規則')
    if not(c and atr and atr>0 and res and ma20 and ma60):blocks.append('不足完整均線、ATR或壓力')
    result={'version':'17.0.0','symbol':stock['symbol'],'name':stock.get('name'),'sector':stock.get('sector',''),
      'as_of':at.isoformat(),'quote_date':last.get('date'),'reference_price':c,
      'original_code':d.get('code'),'original_label':d.get('label'),'research_score':d.get('score'),
      'account':a,'recommended_live_shares':0,'live_ordering_enabled':False,'forecast_expected_return_pct':None,
      'forecast_reason':'尚無前瞻登記的v17策略驗證；不以目標報酬或舊標籤平均冒充預測',
      'max_holding_sessions':int(a['holding_sessions']),'review_after_sessions':5,
      'holding_basis':'風控預設10交易日、第5日複查，不是回測選出的最佳天數',
      'original_snapshot_preserved':True,'quarantined_price_count':len(issues),'blocks':blocks,'no_leverage':True}
    if c and atr and atr>0 and res and ma20 and ma60:
        stop=floor_tick(max(tick(c,etf),c-2*atr),etf);target=floor_tick(res,etf)
        tax=.001 if etf else .003;buyfactor=(1+a['slippage'])*(1+a['commission_rate']);sellfactor=(1-a['slippage'])*(1-a['commission_rate']-tax)
        cap=(target+a['min_reward_risk']*stop)*sellfactor/((1+a['min_reward_risk'])*buyfactor)
        upper=floor_tick(min(c,cap),etf);sized={'quantity':0,'reason':'價位無效'}
        for _ in range(500):
            if not stop<upper<target:break
            sized=size_position(upper,stop,target,a,etf,stock.get('sector',''))
            if not sized['quantity'] or (sized['net_reward_risk'] or 0)>=a['min_reward_risk']:break
            upper=floor_tick(upper-tick(upper,etf),etf)
        lower=ceil_tick(max(stop+tick(c,etf),upper-.25*atr),etf)
        if c<=ma20 or c<=ma60:blocks.append(f'趨勢未過：{c:g}須高於MA20 {ma20:.2f}及MA60 {ma60:.2f}')
        if upper<max(ma20,ma60):blocks.append('合格價帶低於趨勢線，條件互斥：等新日K重算，不掛單抄底')
        if sized['quantity']<=0:blocks.append(sized['reason'])
        if target<=upper or stop>=upper:blocks.append('沒有可用進場、停損、目標順序')
        result.update(entry_band=[lower,upper],entry_limit=upper,stop_price=stop,target_price=target,
          conditional_size=sized,conditional_shares=sized['quantity'],first_order_shares=sized['quantity'],additional_order_shares=0,
          sequence='單筆規劃，不自動攤平、不追價；加碼須重算剩餘風險與費用',
          trigger='新鮮完整日K、原條件通過、現價在價帶內；僅下一有效交易日有效',
          expiry_rule='下一有效交易日未成交或跳空高於上限即取消，不改無上限市價單',
          stop_rule=f'停損參考 {stop:g} 元；跳空以可成交價處理，不能保證損失上限',
          target_rule=f'{target:g} 元以全部部位結束情境；此為近20日壓力，不是預測目標',
          time_exit=f'含進場日第 {int(a["holding_sessions"])} 個實際交易日收盤退出；第5日複查',
          thesis_exit='正式下修、原事件被否認或風控失效時重新評估；不以天數取代停損',
          lot_warning='零股不能保證09:00整股開盤成交；實際成交價需重算' if a['lot_size']==1 else '整股1000股單位；停牌或鎖死漲跌停可能無法成交')
    result['paper_candidate']=not blocks;result['status']='blocked' if blocks else 'paper_only'
    result['status_label']='本次不下單：先修資料或條件' if blocks else '僅條件式試買，未證實優勢'
    result['historical_reference']={str(h):history_reference(records or [],stock,snapshot_at,h) for h in HORIZONS}
    return result

def batch_plans(snapshot,records,account=None):
    a=validate_account(account or {});plans=[];held=list(a['holdings']);cash=a['available_cash']
    for s in sorted(snapshot['stocks'],key=lambda s:s.get('decision',{}).get('score',0),reverse=True):
        p=make_plan(s,snapshot['generated_at'],{**a,'holdings':held,'available_cash':cash},records)
        if p['paper_candidate'] and p.get('conditional_shares',0)>0:
            z=p['conditional_size'];q=p['conditional_shares'];cash-=z['buy_cash']
            held.append({'symbol':s['symbol'],'sector':s.get('sector',''),'market_value':q*p['entry_limit'],'planned_risk':z['planned_stop_loss']})
            p['paper_allocated_shares']=q
        else:p['paper_allocated_shares']=0
        plans.append(p)
    return {'version':'17.0.0','as_of':snapshot['as_of'],'generated_at':snapshot['generated_at'],'created_at':datetime.now(timezone.utc).isoformat(),'mode':'retrospective_plan','account':a,
      'real_orders_enabled':False,'plans':plans,'paper_reserved_cash':round(a['available_cash']-cash,2),
      'note':'按分數依序保留共享試買預算；個別conditional_shares不是每檔同時可買的量'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--audit');p.add_argument('--out');p.add_argument('--account');a=p.parse_args();root=Path(a.root)
    snap=read(root/'data/latest.json');records=read(a.audit or root/'data/evaluation/audit.json').get('records',[])
    out=a.out or root/'data/plans/latest.json';payload=batch_plans(snap,records,read(a.account) if a.account else {})
    payload['source_snapshot_sha256']=hashlib.sha256((root/'data/latest.json').read_bytes()).hexdigest()
    write(out,payload)
    if not a.out:
        import json
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:12]
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        write(root/'data/plan_runs'/f'{stamp}-{digest}.json',payload)
    print(out)
if __name__=='__main__':main()
