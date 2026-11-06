"""Deterministic drawdown/stabilisation research. No bottom probability.
Rules are hypotheses, not empirically calibrated triggers. Never modifies
saved orders, original scores, position size or user risk limits.
"""
from __future__ import annotations
import math
from datetime import datetime, date, timedelta
from stocklab16.common import number, dt
from stocklab16.indicators import enrich
from stocklab17.hygiene import clean_bars
from stocklab17.calendar import expected_close, covered, is_session

LABELS={
 'missing':'價格樣本不足', 'stale':'行情落後，僅能回看', 'corporate_action':'公司行動待調整',
 'falling':'續破低／跌勢仍強', 'oversold':'跌深超賣，尚無止跌確認',
 'rebound':'反彈出現，未確認築底', 'stabilizing':'短線止跌條件形成',
 'reclaim':'回收中期均線，研究恢復', 'neutral':'尚無跌深買點條件'}

def pct(a,b):return (a/b-1)*100 if a is not None and b and b>0 else None
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def rounded(x,n=3):return round(x,n) if finite(x) else x

def diagnose(bars,cutoff,market=None,flow=None,calendar_check=True):
 clean,quarantine=clean_bars(bars,cutoff=cutoff)
 rows=enrich(sorted(clean,key=lambda x:x['date']))
 base={'version':'downside194-v1','computed_at':cutoff,'price_date':rows[-1]['date'] if rows else None,
  'bottom_confirmed':False,'bottom_probability':None,'is_prediction':False,'changes_original_score':False,
  'changes_orders':False,'quarantined':len(quarantine),'metrics':{},'checks':[],
  'news_required_for_price_diagnosis':False,
  'limitations':['判斷是可重算條件，不是已證明低點；超賣不等於見底',
   '使用截至切點的完整日K；不提供即時成交或未來底部',
   '門檻是研究假設，尚未用未見樣本校準；不能以此直接放寬原交易門檻']}
 def finish(code,reason,next_step):
  return {**base,'state':code,'label':LABELS[code],'reason':reason,'next_step':next_step}
 if len(rows)<21:return finish('missing',f'只有{len(rows)}根有效日K；至少21根才比較20日變動','補價，不把缺值當成市場平穩')
 # Do not call 5/20 observations 'trading days' when a required session is missing.
 observed_days={x['date'] for x in rows[-21:]};day=date.fromisoformat(rows[-21]['date']);end=date.fromisoformat(rows[-1]['date']);gaps=[]
 while day<=end:
  if is_session(day.isoformat()) and day.isoformat() not in observed_days:gaps.append(day.isoformat())
  day+=timedelta(days=1)
 if gaps:
  base['missing_sessions']=gaps
  return finish('missing','價量窗口缺交易日：'+', '.join(gaps[:4]),'先補齊同口徑行情，不把缺日跳過後稱作5／20日績效')
 last=rows[-1];prev=rows[-2];c=last['close'];o=last['open'];h=last['high'];l=last['low']
 window=rows[-60:];last20=rows[-20:];prior20=rows[-21:-1]
 if any(x.get('corporate_action') for x in window):
  return finish('corporate_action','窗口跨除權息／拆股；未做同口徑總報酬調整','先處理公司行動，不把機械除息誤判成暴跌')
 ma5=last.get('ma5');ma20=last.get('ma20');ma60=last.get('ma60');rsi=last.get('rsi');atr=last.get('atr')
 peak=max(x['high'] for x in window);prior_low=min(x['low'] for x in prior20)
 vol_hist=[x['volume'] for x in prior20];avgvol=sum(vol_hist)/len(vol_hist)
 volratio=last['volume']/avgvol if avgvol else None
 ret1=pct(c,prev['close']);ret5=pct(c,rows[-6]['close']);ret20=pct(c,rows[-21]['close']);drawdown=pct(c,peak)
 ma20_slope=pct(ma20,rows[-6].get('ma20'))
 relative=None
 if market and market.get('price_date')==last['date']:
  bm=market.get('metrics',{}).get('return_5d_pct')
  relative=ret5-bm if finite(bm) else None
 lows=[x['low'] for x in rows[-3:]];higher_lows=lows[0]<lows[1]<=lows[2]
 prior_floor=min(x['low'] for x in rows[-23:-3]) if len(rows)>=23 else None
 no_new_low3=all(x['low']>=prior_floor for x in rows[-3:]) if prior_floor else None
 reclaim5=bool(ma5 and c>ma5);reclaim20=bool(ma20 and c>ma20)
 hist=[x.get('histogram') for x in rows[-3:]]
 momentum_improving=all(finite(x) for x in hist) and hist[0]<hist[1]<hist[2]
 new_low=l<prior_low
 span=h-l;close_location=(c-l)/span if span>0 else None
 lower_wick=(min(c,o)-l)/span if span>0 else None
 metrics={'close':c,'open':o,'high':h,'low':l,'return_1d_pct':ret1,'return_5d_pct':ret5,'return_20d_pct':ret20,
  'observed_window':len(window),'drawdown_from_60high_pct':drawdown,'prior20_low':prior_low,
  'rsi14':rsi,'atr14':atr,'atr_pct':atr/c*100 if atr else None,'ma5':ma5,'ma20':ma20,'ma60':ma60,
  'ma20_slope5_pct':ma20_slope,'volume_ratio_prior20':volratio,'close_in_daily_range':close_location,
  'lower_wick_fraction':lower_wick,'relative_5d_pct':relative,'reference_pressure':max(x['high'] for x in last20)}
 base['metrics']={k:rounded(v) for k,v in metrics.items()}
 def check(key,label,passed,evidence):
  base['checks'].append({'key':key,'label':label,'status':'missing' if passed is None else 'pass' if passed else 'fail','evidence':evidence})
 check('stop_new_lows','連3根不破先前區間低點',no_new_low3,f'最近3低點 {[rounded(x,2) for x in lows]}；之前20日低點 {rounded(prior_floor)}')
 check('higher_lows','短線低點墊高',higher_lows,f'最近3低點 {[rounded(x,2) for x in lows]}')
 check('ma5','收回5日均線',reclaim5,f'收盤 {c:.2f}／MA5 {ma5:.2f}')
 check('ma20','收回20日均線',reclaim20,f'收盤 {c:.2f}／MA20 {ma20:.2f}')
 check('volume','上漲時有量能支持',None if volratio is None else ret1>0 and volratio>=1.2,f'當日 {ret1:+.2f}%；量／前20日均量 {volratio:.2f}' if volratio is not None else '缺量')
 check('momentum','MACD柱連3期改善',momentum_improving if all(finite(x) for x in hist) else None,f'近3期MACD柱 {[rounded(x) for x in hist]}')
 check('relative','5日相對大盤不弱',None if relative is None else relative>=0,f'個股減基準5日報酬 {rounded(relative)} 個百分點；需相同價格日')
 latest_flow=flow or {};flow_net=latest_flow.get('foreign_net_5') if latest_flow.get('status')=='available' else None
 check('flow','外資短期賣壓改善',flow_net>=0 if finite(flow_net) else None,
       f'5期淨流向 {flow_net} 股；不等於存量成本' if finite(flow_net) else '法人窗口缺少同時點資料；未當成買超或停止賣超')
 below=c<ma20;oversold=(rsi is not None and rsi<30) or drawdown<=-15
 shock=ret1<=-3 or ret5<=-8
 if below and (new_low or shock):
  if close_location is not None and close_location>.65 and lower_wick is not None and lower_wick>.3:
   code='rebound';reason=f'5日 {ret5:+.2f}%、距近高 {drawdown:+.2f}%；出現下影線／回收日內跌幅，但還不是底部確認'
  else:code='falling';reason=f'5日 {ret5:+.2f}%、距近高 {drawdown:+.2f}%；'+('再破前20日低點' if new_low else '仍有急跌壓力')
 elif higher_lows and no_new_low3 and reclaim20 and ma20_slope is not None and ma20_slope>=0:
  code='reclaim';reason='短線低點墊高且收回20日線，均線斜率未惡化；僅達研究恢復條件'
 elif no_new_low3 and higher_lows and reclaim5 and momentum_improving:
  code='stabilizing';reason='連3期未破前區間低點、低點墊高、收回5日線且動能改善'
 elif below and reclaim5 and ret1>0:
  code='rebound';reason='反彈收回5日線，但中期趨勢或低點結構未完成'
 elif oversold:code='oversold';reason=f'RSI {rsi:.1f}、近高回落 {drawdown:+.2f}%；超賣不保證反彈' if rsi is not None else f'回落 {drawdown:+.2f}%，缺RSI'
 else:code='neutral';reason=f'5日 {ret5:+.2f}%；尚未形成固定規則中的跌深止跌組合'
 stop=max(.01,min(x['low'] for x in rows[-5:])-.5*atr) if atr else None
 target=metrics['reference_pressure']
 trigger=max(last['high'],ma5)
 rr=(target-c)/(c-stop) if stop and stop<c else None
 threshold_price=(target+1.5*stop)/2.5 if stop else None
 base['research_levels']={'reference_price':c,'next_session_confirmation_above':rounded(trigger,2),
  'invalidation_below':rounded(stop,2),'prior20_low':rounded(prior_low,2),'pressure_scenario':rounded(target,2),
  'gross_reward_risk':rounded(rr),'max_price_for_gross_rr_1_5':rounded(threshold_price,2),
  'levels_are_scenarios_not_targets':True,'note':'下一日需重新報價；含成本後空間更小，跳空／流動性會改變損失'}
 market_state=(market or {}).get('state');crisis=market_state in ('falling','oversold','stale','missing','corporate_action')
 stage=2 if code=='reclaim' else 1 if code=='stabilizing' else 0
 if crisis:stage=min(stage,1)
 base['research_stage']=stage
 base['risk_budget_fraction_for_research']=[0,.25,.5][stage]
 base['add_plan']={'status':'conditional_review' if stage else 'not_yet',
  'label':'可建立獨立止跌試驗，不代表原策略放行' if stage else '只追蹤；不因跌幅大而自動加碼',
  'assumption':'固定研究分段0／25%／50%原單筆風險額度，不是最佳化配置；不得提高總風險',
  'requires_existing_positions':True,'auto_orders':False,
  'existing_holder':'先把既有股數到停止價的潛在損失與退出成本占用額度扣掉；超標就不加碼',
  'non_holder':'必須先確認止跌與成本後空間；不用買入股數補出資料不足的結論'}
 check('market','大盤是否脫離急跌',False if crisis else None if not market else True,
       '未提供基準時不推定安全' if market is None else '大盤狀態：'+str(market.get('label')))
 next_step=f'觀察下一完整交易日是否守住 {prior_low:.2f}、收回MA5 {ma5:.2f}，並核對量比與動能；跌破停止情境 {stop:.2f} 不增加同一方向風險' if stop else '先補ATR與停止價格'
 result=finish(code,reason,next_step)
 if calendar_check:
  try:expected=expected_close(cutoff);fresh=covered(expected) and last['date']==expected
  except Exception:expected=None;fresh=False
  result['expected_price_date']=expected
  if not fresh:
   result['underlying_price_state']=code;result['state']='stale';result['label']=LABELS['stale']
   result['reason']=f'需要 {expected or "可核對交易日"} 完整行情，現有 {last["date"]}；保留價量觀察但不給新加碼'
   result['research_stage']=0;result['risk_budget_fraction_for_research']=0;result['add_plan']['status']='blocked_stale'
 return result

def size_addition(entry,stop,target,cash,position_cap,risk_budget,existing_shares=0,current=None,
                  fee_rate=.001425,min_fee=20,sell_tax=.003,slippage=.001,risk_fraction=.25):
 """Conservative research sizing; NOT a trade or expectation. Mark-to-stop risk."""
 vals=[entry,stop,target,cash,position_cap,risk_budget,existing_shares,fee_rate,min_fee,sell_tax,slippage,risk_fraction]
 if any(not finite(x) or x<0 for x in vals) or not 0<stop<entry or not 0<=risk_fraction<=1 or target<=entry or not float(existing_shares).is_integer():
  return {'status':'invalid','shares':0,'reason':'價格／風險／費用輸入無效'}
 mark=current if finite(current) else entry
 def fee(x):return max(min_fee,x*fee_rate)
 existing_risk=max(0,existing_shares*mark-(existing_shares*stop*(1-slippage)*(1-sell_tax)-fee(existing_shares*stop*(1-slippage)))) if existing_shares else 0
 remaining=max(0,risk_budget-existing_risk)
 # Exposure cap includes existing current market value.
 cash_cap=max(0,min(cash,position_cap-existing_shares*mark))
 allowed=min(remaining,risk_budget*risk_fraction)
 def costs(q,exit_):
  buy=q*entry*(1+slippage);sale=q*exit_*(1-slippage)
  return buy+fee(buy),sale-fee(sale)-sale*sell_tax
 lo,hi=0,int(cash_cap/entry)
 while lo<hi:
  q=(lo+hi+1)//2;b,s=costs(q,stop)
  if b<=cash_cap and b-s<=allowed:lo=q
  else:hi=q-1
 if not lo:return {'status':'no_capacity','shares':0,'existing_risk':round(existing_risk,2),'remaining_risk':round(remaining,2),'reason':'扣除既有部位、成本及分段風險後，沒有一股空間'}
 buy,loss_exit=costs(lo,stop);_,gain_exit=costs(lo,target)
 loss=buy-loss_exit;gain=gain_exit-buy
 if gain<=0 or (loss>0 and gain/loss<1.5):return {'status':'cost_space_insufficient','shares':0,'risk_limited_shares':lo,'existing_risk':round(existing_risk,2),'remaining_risk':round(remaining,2),'reason':'含成本後上檔空間未達1.5研究門檻；不為湊出股數忽略費用'}
 return {'status':'scenario_only','shares':lo,'buy_cost':round(buy,2),'stop_scenario_loss':round(loss,2),
   'target_scenario_profit':round(gain,2),'net_reward_risk':round(gain/loss,3) if loss else None,
   'existing_risk':round(existing_risk,2),'remaining_risk':round(remaining,2),
   'expected_return':None,'auto_orders':False,'warning':'目標情境不是預測；需完整個人部位與核對後行情，原試單不修改'}
