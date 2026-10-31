"""Foreign-flow support proxy. NOT the institutions' inventory or true cost basis."""
import math
from stocklab192.schema import timestamp

def defense(candles,flows,cutoff,window=20,min_sessions=5):
 end=timestamp(cutoff);actions=[b for b in candles if b.get('corporate_action') and b.get('date','')<=cutoff[:10]];bars={b['date']:b for b in candles if b.get('date') and b['date']<=cutoff[:10] and all(isinstance(b.get(k),(int,float)) and math.isfinite(b[k]) for k in ('high','low','close','volume')) and b['volume']>0 and 0<b['low']<=b['close']<=b['high'] and not b.get('corporate_action')}
 valid={}
 for r in flows:
  try:
   if timestamp(r['available_at'])>end or r['date']>cutoff[:10]:continue
   net=r['foreign_net'];d=r['date']
   if isinstance(net,bool) or not isinstance(net,(int,float)) or not math.isfinite(net) or d not in bars:continue
   # one row per day; do not count duplicate downloads as additional flow.
   valid[d]=r
  except (ValueError,KeyError,TypeError):continue
 dates=sorted(bars)[-window:];matched=[d for d in dates if d in valid];newest=dates[-1] if dates else None
 base={'label':'外資流向支撐代理線（非真實成本）','method_version':'net-buy-typical-price-v1','cutoff':cutoff,'window_sessions':window,'matched_sessions':len(matched),'required_sessions':min_sessions,'actual_institutional_cost':False,'value':None,'alert':'資料不足','status':'missing','formula':'Σ[當日典型價×max(外資淨買股數,0)] / Σmax(外資淨買股數,0)','limitations':['不含外資實際成交價與存量部位，不是外資真實成本或保證支撐','只用截至分析時間已取得的法人資料；不同市場分開處理','缺交易日、不足樣本、沒有淨買時不造線；不以此單獨買進']}
 if actions and dates and any(b['date']>=dates[0] for b in actions):return {**base,'status':'corporate_action','alert':'窗口跨公司行動；先處理調整，不能連線'}
 if len(matched)<min_sessions:return base
 if newest not in valid:return {**base,'status':'stale','alert':'最新交易日法人資料尚缺'}
 pos=[d for d in matched if valid[d]['foreign_net']>0];weight=sum(valid[d]['foreign_net'] for d in pos)
 if weight<=0:return {**base,'status':'no_positive_net_buy','alert':'窗口內沒有正淨買，不能估計代理線'}
 # Do not bridge a corporate action or any hole in the matched price window.
 if len(matched)!=len(dates):return {**base,'status':'partial','alert':'窗口法人資料不連續，先補齊再估計'}
 value=sum(((bars[d]['high']+bars[d]['low']+bars[d]['close'])/3)*valid[d]['foreign_net'] for d in pos)/weight
 nets=[valid[d]['foreign_net'] for d in matched];close=bars[newest]['close'];net5=sum(nets[-5:]);selling=len(nets)>=3 and all(n<0 for n in nets[-3:])
 alert='跌破代理線＋近5日淨賣' if close<value and net5<0 else '接近代理線（距離2%內）' if abs(close/value-1)<=.02 else '觀察中'
 if selling and close<value:alert='跌破代理線＋連3期淨賣'
 return {**base,'status':'available','value':round(value,4),'reference_close':close,'distance_pct':round((close/value-1)*100,3),'positive_buy_sessions':len(pos),'foreign_net_5':net5,'three_session_net_selling':selling,'alert':alert}
