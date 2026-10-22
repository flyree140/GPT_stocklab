"""Archive-only daily report and cash-constrained counterfactual portfolios.
No tuning to observed outcomes; original instructions and research variants stay separate.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, math
from pathlib import Path
from datetime import date,timedelta
from stocklab17.audit import read,write,outcome,HORIZONS,run as audit_run
from stocklab17.calendar import clock,parse_time,is_session,expected_close,future_sessions,SEED
from stocklab17.hygiene import clean_bars
from stocklab17.planner import make_plan

def fee(value,minimum=20):return round(max(minimum,value*.001425),2)
def buy(q,p):
    gross=round(q*p*1.001,2);comm=fee(gross)
    return {'cash':round(gross+comm,2),'gross':gross,'fee':comm,'price':p}
def sell(q,p,etf=False):
    gross=round(q*p*.999,2);comm=fee(gross);tax=round(gross*(.001 if etf else .003),2)
    return {'cash':round(gross-comm-tax,2),'gross':gross,'fee':comm,'tax':tax,'price':p}
def settle(day):return future_sessions(day+'T23:59:00+08:00',2)[-1]
def safe_days(start,end):
    d=date.fromisoformat(start)
    while d.isoformat()<=end:
        yield d.isoformat();d+=timedelta(days=1)

def scenario(kind,raw,market,start,end,monthly=4000):
    """One account, one position; sell receipts unavailable until T+2; no same-day reentry.
    ranked: original top pick, <=NT$4,000 allocation, 5 sessions; not original buy instruction.
    gated: original ATR/support risk map, fresh quotes, no chasing, risk<=200, <=10 sessions.
    """
    cash=0.;pending=[];pos=None;trades=[];days=[];deposits=0.;month=None;refused=[]
    allruns=sorted(raw,key=lambda x:x['generated_at']);valid_sessions=sorted(market.get('0050.TW',{}))
    for day in safe_days(start,end):
        injection=0.
        if day[:7]!=month:injection=monthly;cash+=injection;deposits+=injection;month=day[:7]
        for rec in pending[:]:
            if rec['date']<=day:cash+=rec['cash'];pending.remove(rec)
        acts=[];sold_today=False
        if day in valid_sessions:
            if pos:
                b=market.get(pos['symbol'],{}).get(day)
                if b:
                    pos['sessions']+=1;pos['last_close']=b['close'];pos['last_date']=day
                    px=None;why=''
                    if b.get('corporate_action'):
                        pos['valuation_unresolved']=True
                        acts.append('公司行動：停止績效結算，待權益資料核對')
                    if not pos.get('valuation_unresolved') and b['high']!=b['low']:
                        if kind=='gated':
                            if b['open']<=pos['stop']:px=b['open'];why='跳空停損（不假設停損價成交）'
                            elif b['open']>=pos['target']:px=pos['target'];why='開盤跨越停利，保守採目標'
                            elif b['low']<=pos['stop']:px=pos['stop'];why='碰停損；同日雙觸價採停損優先'
                            elif b['high']>=pos['target']:px=pos['target'];why='碰停利假設'
                        if px is None and pos['sessions']>=pos['max_hold']:px=b['close'];why='固定持有期限到期'
                    if px is not None:
                        sv=sell(pos['q'],px,pos['symbol'].startswith('00'))
                        trade={**pos,'exit_date':day,'exit_price':px,'exit_reason':why,'net_proceeds':sv['cash'],'sell_fee':sv['fee'],'tax':sv['tax'],'pnl':round(sv['cash']-pos['buy_cash'],2),'roi_pct':round((sv['cash']/pos['buy_cash']-1)*100,4),'settlement_date':settle(day)}
                        trades.append(trade);pending.append({'cash':sv['cash'],'date':settle(day)});acts.append(f'賣 {pos["name"]} {pos["q"]}股；損益 {trade["pnl"]:+.2f}')
                        pos=None;sold_today=True
            if not pos and not sold_today:
                known=[r for r in allruns if parse_time(r['generated_at'])<clock(day)]
                if known:
                    stamp=known[-1]['generated_at'];universe=[r for r in known if r['generated_at']==stamp]
                    cand=[r for r in universe if not r.get('issues') and not r['etf']]
                    if kind=='strict':cand=[r for r in cand if r['original_code']=='conditional_buy']
                    else:cand=[r for r in cand if r['top_pick']]
                    cand.sort(key=lambda r:(-(r.get('score') or 0),r['symbol']))
                    for r in cand[:1]:
                        b=market.get(r['symbol'],{}).get(day)
                        if not b or b.get('corporate_action') or b['high']==b['low']:refused.append({'date':day,'symbol':r['symbol'],'reason':'缺日K／公司行動／不可假設成交'});continue
                        # IMPORTANT: never reject candidates using future holding-window availability.
                        entry=b['open'];stop=r.get('stop');target=r.get('resistance');limit=r['quote']
                        budget=min(cash,monthly);q=max(0,math.floor((budget-20)/(entry*1.002425)))
                        if kind=='gated':
                            if r['quote_date']!=expected_close(day+'T08:59:00+08:00'):
                                refused.append({'date':day,'symbol':r['symbol'],'reason':'訊號價格過期'});continue
                            if r['original_code'] in ('avoid','insufficient') or not stop or not target or not 0<stop<entry<target or entry>limit:
                                refused.append({'date':day,'symbol':r['symbol'],'reason':'不追價／無有效風險價位'});continue
                            while q and (buy(q,entry)['cash']>budget or buy(q,entry)['cash']-sell(q,stop)['cash']>200):q-=1
                            if not q or (sell(q,target)['cash']-buy(q,entry)['cash'])/max(.01,buy(q,entry)['cash']-sell(q,stop)['cash'])<1.5:
                                refused.append({'date':day,'symbol':r['symbol'],'reason':'扣費後空間不足'});continue
                        while q and buy(q,entry)['cash']>budget:q-=1
                        if not q:refused.append({'date':day,'symbol':r['symbol'],'reason':'資金或價格不足一股'});continue
                        bv=buy(q,entry);cash-=bv['cash'];pos={'symbol':r['symbol'],'name':r['name'],'q':q,'signal_as_of':r['as_of'],'signal_generated_at':stamp,'source_sha256':r['source_sha256'],'entry_date':day,'entry_price':entry,'buy_cash':bv['cash'],'buy_fee':bv['fee'],'original_label':r['original_label'],'original_score':r['score'],'sessions':1,'max_hold':10 if kind=='gated' else 5,'stop':stop,'target':target,'last_close':b['close'],'last_date':day}
                        acts.append(f'買 {pos["name"]} {q}股 @ {entry:g}；成本 {bv["cash"]:.2f}')
                        # Entry-day day-bar ambiguity: conservative immediate stop first if touched.
                        if kind=='gated' and (b['low']<=stop or b['high']>=target):
                            px=stop if b['low']<=stop else target;sv=sell(q,px)
                            tr={**pos,'exit_date':day,'exit_price':px,'exit_reason':'進場日觸價，停損優先假設','net_proceeds':sv['cash'],'sell_fee':sv['fee'],'tax':sv['tax'],'pnl':round(sv['cash']-bv['cash'],2),'roi_pct':round((sv['cash']/bv['cash']-1)*100,4),'settlement_date':settle(day)}
                            trades.append(tr);pending.append({'cash':sv['cash'],'date':settle(day)});acts.append(f'同日退出；損益 {tr["pnl"]:+.2f}');pos=None
        unresolved=bool(pos and pos.get('valuation_unresolved'))
        marked=sell(pos['q'],pos['last_close'],pos['symbol'].startswith('00'))['cash'] if pos and not unresolved else 0
        total=cash+sum(x['cash'] for x in pending)+marked
        days.append({'date':day,'injection':injection,'deposits':round(deposits,2),'spendable_cash':round(cash,2),'unsettled_sales':round(sum(x['cash'] for x in pending),2),'holding':pos['name'] if pos else '', 'shares':pos['q'] if pos else 0,'mark_date':pos['last_date'] if pos else '', 'estimated_liquidation':None if unresolved else round(marked,2),'equity':None if unresolved else round(total,2),'pnl':None if unresolved else round(total-deposits,2),'valuation_complete':not unresolved,'action':'；'.join(acts) or ('休市／無行情，不成交' if day not in valid_sessions else '保留現金／續持，不強迫交易')})
    last=days[-1];return {'kind':kind,'monthly_contribution':monthly,'salary_assumption':40000,'start':start,'end':end,'deposits':deposits,'equity':last['equity'],'net_pnl':last['pnl'],'simple_return_pct':None if last['pnl'] is None else round(last['pnl']/deposits*100,4),'realized_pnl':round(sum(t['pnl'] for t in trades),2),'trades':trades,'daily':days,'open_position':pos,'refused':refused,'status':'unresolved_corporate_action' if pos and pos.get('valuation_unresolved') else 'reconstructed','minimum_commission':20,'costs':'手續費0.1425%雙邊、每邊最低20元；滑價0.1%雙邊；股票賣出稅0.3%；按T+2凍結賣款。'}

def run(root,out):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    auditfile=root/'data/evaluation/audit.json'
    if not auditfile.exists():audit_run(root,root/'data/evaluation')
    audit=read(auditfile);market={};quarantine=[]
    for p in (root/'data/market').glob('*.json'):
        x=read(p);bars,issues=clean_bars(x['candles']);market[x['symbol']]={b['date']:b for b in bars};quarantine+=issues
    sessions=sorted(market['0050.TW']);manifest=read(root/'data/manifest.json');rows=[];all_raw=[]
    # Raw archive used only after validating per-file digests, same as audit.
    import csv as csvmod
    rawfile=root/'data/evaluation/01_original_all_runs.csv'
    # Use richer records reconstructed from original snapshots, not stripped CSV.
    candidates={}
    for m in manifest['snapshots']:
        for r in m.get('runs',[m]):
            p=root/r['path']
            if not p.exists():continue
            if r.get('sha256') and hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:continue
            snap=read(p)
            if snap.get('demo') or snap.get('mode') in ('reanalysis','recomputed','historical_reconstruction') or snap.get('derived_from'):continue
            stamp=snap['generated_at'];d=snap['as_of']
            if d not in candidates or stamp>candidates[d][0]:candidates[d]=(stamp,snap,r)
            for s in snap['stocks']:
                last=s.get('candles',[{}])[-1];dec=s['decision'];issues=[]
                if not last or not is_session(last['date']):issues.append('invalid_snapshot_price')
                if last and clock(last['date'],13,30)>parse_time(stamp):issues.append('future_price')
                ent=next((day for day in sessions if clock(day)>parse_time(stamp) and day>last.get('date','')),None)
                all_raw.append({'symbol':s['symbol'],'name':s['name'],'sector':s.get('sector',''),'as_of':d,'generated_at':stamp,'quote_date':last.get('date'),'quote':last.get('close'),'entry_date':ent,'original_label':dec.get('label'),'original_code':dec.get('code'),'score':dec.get('score'),'top_pick':s['symbol'] in snap.get('top_picks',[]),'etf':s['symbol'].startswith('00'),'source_sha256':r.get('sha256',hashlib.sha256(p.read_bytes()).hexdigest()),'source_path':r['path'],'issues':issues,'stop':dec.get('plan',{}).get('stop_reference'),'resistance':dec.get('plan',{}).get('resistance'),'next_action':dec.get('next_action'),'new_investor':dec.get('new_investor'),'coverage':dec.get('coverage')})
    for day,(stamp,snap,src) in sorted(candidates.items()):
        sr=[r.copy() for r in all_raw if r['generated_at']==stamp]
        # Manifest repeated indexes could duplicate same run; keep per-symbol original.
        sr=list({r['symbol']:r for r in sr}.values())
        for r in sr:
            for h in HORIZONS:r['h'+str(h)]={'status':'pending'} if not r['entry_date'] else {'status':'invalid_signal'} if r['issues'] else outcome(r,market,sessions,h,market['0050.TW'])
        rows.append({'date':day,'generated_at':stamp,'source_path':src['path'],'source_sha256':src.get('sha256'),'stocks':sorted(sr,key=lambda r:r['symbol']),'top_picks':snap.get('top_picks',[]),'strict_buys':sum(s['original_code']=='conditional_buy' for s in sr),'strict_action':('有原始買進標籤，但成交另依資金與價格假設' if any(s['original_code']=='conditional_buy' for s in sr) else '原始條件未通過，無買進；非實際券商交易')})
    start=rows[0]['date'];end=rows[-1]['date'];scenarios={k:scenario(k,all_raw,market,start,end) for k in ('strict','ranked','gated')}
    payload={'version':'18.0.0','source':'使用者上傳GPT_stocklab-main.zip','archive_end':end,'price_end':sessions[-1],'date_count':len(rows),'symbol_count':len({r['symbol'] for x in rows for r in x['stocks']}),'daily':rows,'scenarios':scenarios,'audit_summary':audit['summary'],'limits':['歷史檔價格未逐筆與交易所獨立核對；不是券商成交紀錄','股數情境以普通日K估算零股；9:10實際零股價與排隊不明','資料有異常與公司行動旗標，不補造價格','規則為事後明訂，不是前瞻驗證；不可保證收益','最低手續費20元、T+2資金凍結與每月4000預算會使結果不同於上次預覽',f'月薪40000不等於全數投資，期間投入{scenarios["strict"]["deposits"]:g}元，收入不是帳戶損益','資產含未出售部位的假設淨變現估值；未實現和已實現分開']}
    write(out/'daily-report.json',payload)
    def csvwrite(name,data):
        fields=list(dict.fromkeys(k for x in data for k in x)) if data else ['symbol','name','entry_date','exit_date','q','pnl']
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in data)
    csvwrite('01_all_days_all_stocks.csv',[r for day in rows for r in day['stocks']])
    for k,v in scenarios.items():csvwrite(f'02_{k}_daily_cash.csv',v['daily']);csvwrite(f'03_{k}_trades.csv',v['trades'])
    write(out/'methodology.json',{'archive_sha256':None,'calendar':SEED,'fees':{'commission_rate':.001425,'min_fee':20,'slippage':.001,'stock_tax':.003,'etf_tax':.001},'salary':40000,'monthly_contribution':4000,'initial_prior_savings':0,'deposits':[x['date'] for x in scenarios['strict']['daily'] if x['injection']>0],'cash_constraints':'one position, max4000/order, no sale proceeds before T+2','rules_not_optimized':True})
    print(json.dumps({k:{a:v[a] for a in ('equity','net_pnl','simple_return_pct','realized_pnl')} for k,v in scenarios.items()},ensure_ascii=False,indent=2))
    return payload

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--out');a=p.parse_args();run(a.root,a.out or str(Path(a.root)/'data/life'))
if __name__=='__main__':main()
