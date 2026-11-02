/** Transparent diagnostics for complete-day paper executions, not broker orders. */
import * as P from './paper-engine.mjs';
export const PATCH_VERSION = '19.3.3';
export const UPDATE_WINDOWS = [
 {time:'08:17',kind:'research',label:'盤前新聞＋研究；Qwen每批最多6次'},
 {time:'09:17',kind:'price',label:'開盤後檢查；只補前一完整交易日日K'},
 {time:'12:17',kind:'price',label:'午間檢查；當日日K尚未完成，不虛構成交'},
 {time:'14:17',kind:'price',label:'盤後補完整日K；來源未公布會保留等待'},
 {time:'16:17',kind:'price',label:'盤後重試、補前次缺失、更新被動結果'},
 {time:'21:17',kind:'research',label:'晚間新聞＋下一交易日研究；Qwen最多6次'},
 {time:'21:47',kind:'price',label:'晚間補價備援，不使用Qwen'},
];
export function taipeiClock(at = new Date()) {
 const date=new Date(at); if(!Number.isFinite(+date))throw Error('裝置日期無效，請先校正系統時間');
 const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(date).map(p=>[p.type,p.value]));
 return {date:`${parts.year}-${parts.month}-${parts.day}`,hhmm:Number(parts.hour+parts.minute),text:`${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`,timezone:'Asia/Taipei (UTC+8)'};
}
export function latestBarDate(payload){return (payload?.candles||[]).map(r=>r.date).filter(P.dateValid).sort().at(-1)||null;}
export function rowState(row,batch,cal,at=new Date(),market=null){
 if(batch.deletedAt)return {state:'paused',message:'批次在回收桶；試單保留，先還原。'};
 const a=row.account;
 if(!a)return {state:'not_ordered',message:row.proposal?.blocks?.join('；')||'只保存分析，這列未建立試單。'};
 const need=P.settlementNeeds(a,cal,at),pending=a.orders.filter(o=>o.status==='pending'),last=a.orders.at(-1);
 const unresolved=!!a.position||pending.length||a.receivables?.length;
 if(!unresolved){const why=[...a.events].reverse().find(e=>e.type==='unfilled')?.payload?.reason;
  return {state:a.closed.length?'closed':last?.status==='unfilled'?'unfilled':last?.status==='uncertain'?'uncertain':'idle',
   message:a.closed.length?`已完成${a.closed.length}筆虛擬交易。`:why||'沒有待處理指令。',reason:why};}
 if(need.state==='not_closed')return {state:'await_close',date:need.date,pending,message:`有效日${need.date}尚未收盤。日K回算模式不是即時成交；到當日完整行情發布後才判定。`};
 if(need.state==='calendar_missing')return {state:'calendar_missing',message:need.message};
 if(need.state==='cash_day')return {state:'cash_day',date:need.date,message:'只處理現金與待交割，沒有買進指令需成交。'};
 const symbol=need.symbols[0],file=`data/market/${String(symbol).replaceAll('.','_')}.json`;
 if(market){const d=P.diagnoseMarket(market[symbol],symbol,need.date,file);if(!d.ok)return {state:market[symbol]?._transportError?'download_error':'missing_price',date:need.date,symbol,file,
   latest:d.latest||null,message:market[symbol]?._transportError||d.message};}
 return {state:a.position?'holding':'need_price',date:need.date,symbol,file,message:a.position?`持有中；下一步核對${need.date}。`:`等待核對${need.date}開盤及完整日K；目前不是已買進。`};
}
export function changeSummary(before,after){
 let bought=0,sold=0,unfilled=0,sessions=0,errors=0; const observations=after.rows.filter(r=>!r.account).length;
 for(const r of after.rows){if(r.lastError)errors++;const old=before.rows.find(x=>x.symbol===r.symbol)?.account;
  for(const e of r.account?.events?.slice(old?.events?.length||0)||[]){if(e.type==='simulated_buy')bought++;if(e.type==='simulated_sell')sold++;if(e.type==='unfilled')unfilled++;if(e.type==='advance_day')sessions++;}}
 return {bought,sold,unfilled,sessions,errors,observations};
}
export function summaryMessage(r){
 if(!r.batches)return '尚未有啟用中的批次。先看全部配置，再確認合格試單。';
 return `本次核對${r.batches}批：虛擬買進${r.bought}筆、虛擬賣出${r.sold}筆、確定未成交${r.unfilled}筆、日結${r.sessions}次；${r.errors}檔仍需處理。${r.bought===0?'0筆買進不等於沒執行；逐檔原因在下方。':''}`;
}
export function approvalChanged(oldCtx,newCtx,cal){
 return P.canonical(oldCtx.priceEvidence||{})!==P.canonical(newCtx.priceEvidence||{}) || oldCtx.hash!==newCtx.hash || oldCtx.mode!==newCtx.mode || P.decisionSession(oldCtx.at,cal)!==P.decisionSession(newCtx.at,cal);
}
export const STATE_LABELS={not_ordered:'未建立試單',await_close:'等有效日收盤',missing_price:'缺指定日行情',download_error:'下載行情失敗',calendar_missing:'日曆待核對',need_price:'待日K回算',holding:'已虛擬持有',unfilled:'本次未成交',uncertain:'成交無法判定',closed:'已完成虛擬交易',paused:'暫停',cash_day:'待交割／現金日',idle:'無待處理指令'};
