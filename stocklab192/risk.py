"""Illustrative sizing calculator, independent of Qwen. No orders, no forecast.
Amounts/rates are user assumptions, not a broker's exact fee schedule.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
import math

def d(x):
    if isinstance(x,bool):raise ValueError('boolean is not an amount')
    v=Decimal(str(x))
    if not v.is_finite():raise ValueError('finite amount required')
    return v

def cents(x):return d(x).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)

def plan(*,cash=4000,trade_cap=4000,risk_cap=200,entry=100,stop=96,resistance=106,
         desired_net_profit=150,hold_sessions=10,fee_rate=.001425,min_fee=20,sell_tax=.003,slippage=.001,
         current_shares=0,current_mark=None,other_open_risk=0,portfolio_risk_cap=400,
         thesis_confirmed=False,quote_verified=False,forward_validated=False):
    names=dict(cash=cash,trade_cap=trade_cap,risk_cap=risk_cap,entry=entry,stop=stop,resistance=resistance,
               goal=desired_net_profit,fee=fee_rate,min_fee=min_fee,tax=sell_tax,slip=slippage,
               other=other_open_risk,portfolio_cap=portfolio_risk_cap)
    x={k:d(v) for k,v in names.items()}
    if any(v<0 for v in x.values()) or not 0<x['stop']<x['entry'] or x['resistance']<=x['entry']:raise ValueError('invalid budgets/price ordering')
    if any(x[k]>=1 for k in ('fee','tax','slip')):raise ValueError('rates must be fractions, not percentages')
    if isinstance(current_shares,bool) or int(current_shares)!=current_shares or current_shares<0:raise ValueError('shares must be a nonnegative integer')
    if isinstance(hold_sessions,bool) or int(hold_sessions)!=hold_sessions or not 1<=hold_sessions<=60:raise ValueError('hold_sessions integer 1..60')
    def fee(value):return max(x['min_fee'],cents(value*x['fee'])) if value else Decimal(0)
    def buy(q):
        value=x['entry']*(1+x['slip'])*q
        return cents(value+fee(value))
    def sell(q,price):
        value=price*(1-x['slip'])*q
        return cents(value-fee(value)-cents(value*x['tax'])) if q else Decimal(0)
    if current_shares and current_mark is None:raise ValueError('existing holdings need current mark; salary is not capital')
    mark=d(current_mark) if current_shares else Decimal(0)
    if mark<0:raise ValueError('current mark invalid')
    existing_risk=max(Decimal(0),mark*current_shares-sell(current_shares,x['stop']))
    remaining=min(x['risk_cap']-existing_risk,x['portfolio_cap']-x['other']-existing_risk)
    cap=min(x['cash'],x['trade_cap'])
    hi=int(cap/x['entry']);lo=0
    while lo<hi:
        q=(lo+hi+1)//2
        loss=max(Decimal(0),buy(q)-sell(q,x['stop']))
        if buy(q)<=cap and loss<=max(0,remaining):lo=q
        else:hi=q-1
    q=lo
    cost=buy(q);loss=cost-sell(q,x['stop']) if q else Decimal(0)
    gain=sell(q,x['resistance'])-cost if q else Decimal(0)
    target=None
    if q:
        l=x['entry'];h=max(l*2,x['resistance'])
        while sell(q,h)-cost<x['goal']:h*=2
        for _ in range(80):
            mid=(l+h)/2
            if sell(q,mid)-cost>=x['goal']:h=mid
            else:l=mid
        target=float(h.quantize(Decimal('.0001'),rounding=ROUND_HALF_UP))
    blocks=[]
    if not quote_verified:blocks.append('有效行情未核對')
    if not thesis_confirmed:blocks.append('投資假設／原始證據未通過')
    if not forward_validated:blocks.append('新模型尚未通過前瞻驗證；僅影子研究')
    if q==0:blocks.append('可用現金或剩餘風險預算不足')
    if gain<x['goal']:blocks.append('希望淨利高於目前壓力情境，不提高槓桿追求目標')
    return {'scenario_new_shares':q,'permitted_by_inputs_shares':0 if blocks else q,
            'buy_cash':float(cost),'planned_stop_loss':float(loss),'net_at_resistance':float(gain),
            'goal_implied_price_before_tick_rounding':target,'expected_return':None,
            'current_position_risk':float(cents(existing_risk)),'remaining_risk_budget':float(cents(max(0,remaining))),
            'maximum_holding_sessions':hold_sessions,'blocks':blocks,
            'notes':['沒有券商連線；不送出委託','目標價反推不是價格預測；實際委託需按商品跳動單位取整',
                     '既有部位以目前市價到停損的風險計算，不把浮盈當免費籌碼',
                     '加碼合併費用採保守估計；跳空與流動性可能使損失超過預算']}
if __name__=='__main__':
    import json
    print(json.dumps(plan(),ensure_ascii=False,indent=2))
