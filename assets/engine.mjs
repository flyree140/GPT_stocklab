/** Pure simulation/evidence helpers; the same module is unit-tested in Node. */
export const num=(x,f=null)=>x===null||x===undefined||x===''?f:Number.isFinite(Number(x))?Number(x):f;
export const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
export function mergeFavorites(local,remote){
  const merged={...local};
  for(const r of remote){const a=merged[r.symbol];
    // Pending local edits must be resolved by CAS, not blindly merged by a clock.
    if(!a||!a.pending)merged[r.symbol]={...r,pending:false};
  }return merged;
}
export function rawIndicators(rows){
 const out=[];let e12,e26,signal,gain=null,loss=null,k=50,d=50;const closes=[],vol=[],tr=[];
 for(let i=0;i<rows.length;i++){
  const r={...rows[i]},c=num(r.close);if(c===null)continue;
  const prev=closes.at(-1)??c;closes.push(c);vol.push(num(r.volume,0));tr.push(Math.max(r.high-r.low,Math.abs(r.high-prev),Math.abs(r.low-prev)));
  e12=e12===undefined?c:c*2/13+e12*11/13;e26=e26===undefined?c:c*2/27+e26*25/27;const macd=e12-e26;signal=signal===undefined?macd:macd*.2+signal*.8;
  if(closes.length===15){const ds=closes.slice(1).map((x,j)=>x-closes[j]);gain=mean(ds.map(x=>Math.max(x,0)));loss=mean(ds.map(x=>Math.max(-x,0)));}
  else if(closes.length>15){gain=(gain*13+Math.max(c-prev,0))/14;loss=(loss*13+Math.max(prev-c,0))/14;}
  const win=rows.slice(Math.max(0,i-8),i+1);const low=Math.min(...win.map(x=>x.low)),high=Math.max(...win.map(x=>x.high));const rsv=high===low?50:(c-low)/(high-low)*100;k=k*2/3+rsv/3;d=d*2/3+k/3;
  out.push({...r,ma5:closes.length>=5?mean(closes.slice(-5)):null,ma20:closes.length>=20?mean(closes.slice(-20)):null,ma60:closes.length>=60?mean(closes.slice(-60)):null,
   rsi:gain===null?null:gain===0&&loss===0?50:loss===0?100:100-100/(1+gain/loss),macd:closes.length>=26?macd:null,signal:closes.length>=26?signal:null,histogram:closes.length>=26?macd-signal:null,k:closes.length>=9?k:null,d:closes.length>=9?d:null,atr:closes.length>=14?mean(tr.slice(-14)):null});
 }return out;
}
export function simulate(rows,plan,{reveal=false}={}){
 if(!reveal)return {status:'locked',message:'尚未揭曉；没有讀取未來成交資料'};
 const capital=num(plan.capital),days=num(plan.days),stop=num(plan.stop),take=num(plan.take),fee=num(plan.fee,.001425),tax=num(plan.tax,.003),slip=num(plan.slippage,.001),minimum=num(plan.min_fee,20);
 if(!(capital>0)||!Number.isInteger(days)||days<1||days>120||!(stop>0&&stop<1)||!(take>0&&take<3)||fee<0||fee>.05||tax<0||tax>.05||slip<0||slip>.05||minimum<0||minimum>1000)throw Error('請輸入有效資金、整數持有日與合理成本參數');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(plan.date))throw Error('訊號日期不正確');
 const future=rows.filter(r=>r.date>plan.date).sort((a,b)=>a.date.localeCompare(b.date));
 const firstIndex=future.findIndex(r=>num(r.open)>0&&num(r.volume)>0);
 if(firstIndex<0)return {status:'pending',message:'訊號日後尚無可成交開盤價；不以收盤價替代'};
 const bars=future.slice(firstIndex,firstIndex+days);const first=bars[0];const entry=first.open*(1+slip);
 let shares=Math.floor((capital-minimum)/(entry*(1+fee)));
 while(shares>0&&entry*shares+Math.max(minimum,entry*shares*fee)>capital)shares--;
 if(shares<=0)return {status:'pending',message:'資金不足一股與成本'};
 let exit=null,exitDate=null,reason='',held=0,mark=entry;const stopPrice=entry*(1-stop),target=entry*(1+take),marks=[];
 for(const r of bars){
  held++;
  if(r.corporate_action)return {status:'unsupported',message:'跨除權息／拆股；此簡化模型停止計算，不把價格調整當績效'};
  if(!(num(r.open)>0&&num(r.close)>0&&num(r.volume)>0)){marks.push({date:r.date,value:mark});continue;}
  mark=r.close;let fill;
  // Entry-day stop compares next movements, not a pre-entry theoretical mark.
  if(held>1&&r.open<=stopPrice){fill=r.open;reason='跳空跌破停損，以開盤價估計成交';}
  else if(held>1&&r.open>=target){fill=r.open;reason='跳空越過停利，以開盤價估計成交';}
  else if(r.low<=stopPrice){fill=stopPrice;reason=r.high>=target?'同日雙觸及，採保守停損優先':'觸及停損';}
  else if(r.high>=target){fill=target;reason='觸及停利';}
  else if(held===days){fill=r.close;reason='持有期到期收盤';}
  marks.push({date:r.date,value:fill??mark});
  if(fill!==undefined){exit=fill*(1-slip);exitDate=r.date;break;}
 }
 const invested=entry*shares+Math.max(minimum,entry*shares*fee);
 if(exit===null)return {status:'open',entry,entry_date:first.date,shares,held,mark,unrealized:mark*shares-invested,message:'尚未滿持有期／未觸發出場，持倉中，不計入已完成勝率',marks};
 const sale=exit*shares,costs={buy_fee:Math.max(minimum,entry*shares*fee),sell_fee:Math.max(minimum,sale*fee),tax:sale*tax};
 const pnl=sale-costs.sell_fee-costs.tax-invested,returns=pnl/invested*100;
 // Close/estimated-exit marked drawdown, not an unknowable intraday ordering.
 let peak=capital,mdd=0;const equity=marks.map(r=>{const value=capital-invested+r.value*shares;peak=Math.max(peak,value);mdd=Math.min(mdd,(value/peak-1)*100);return {date:r.date,value};});
 const finalValue=capital+pnl;peak=Math.max(peak,finalValue);mdd=Math.min(mdd,(finalValue/peak-1)*100);if(equity.length)equity[ equity.length-1].value=finalValue;
 return {status:'closed',entry,entry_date:first.date,exit,exit_date:exitDate,shares,held,reason,stop_price:stopPrice,target_price:target,costs,pnl,return_pct:returns,equity,max_drawdown_pct:mdd};
}
export function summarize(trades){
 const closed=trades.filter(t=>t.status==='closed'),returns=closed.map(t=>t.return_pct);
 return {count:closed.length,open:trades.filter(t=>['open','pending'].includes(t.status)).length,unsupported:trades.filter(t=>t.status==='unsupported').length,
  win_rate:closed.length?closed.filter(t=>t.pnl>0).length/closed.length*100:null,mean_return:mean(returns),
  note:'逐訊號獨立試買；不串乘重疊交易，不宣稱投資組合年報酬或夏普值'};
}
