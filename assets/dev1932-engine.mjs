/** Independent virtual account per analyzed symbol. Not one real funded portfolio. */
import * as P from './paper-engine.mjs';
export const VERSION='19.3.2';
export const DEFAULT={capital:100000,budget:100000,maxLoss:1000,goal:1500,hold:10,feeRate:.001425,minFee:20,slip:.001,strategy:'candidate',autoExit:true,autoFollow:false};
export function prepare(snapshot,ctx,settings={}){
 const s=P.settings({...DEFAULT,...settings});if(snapshot.stocks.length>100)throw Error('單批上限100檔；避免瀏覽器超載');
 if(new Date(snapshot.generated_at)>new Date(ctx.at))throw Error('來源尚未可用');
 const by=new Set();return snapshot.stocks.map(stock=>{
  if(by.has(stock.symbol))throw Error('同一批股票重複');by.add(stock.symbol);
  const proposal=P.propose(stock,s,ctx);
  return {symbol:stock.symbol,name:stock.name,originalCode:stock.decision?.code,originalLabel:stock.decision?.label,proposal,eligible:proposal.blocks.length===0&&proposal.quantity>0,
   baselineTracked:true,baselineNote:'所有股票均被動追蹤；未通過不硬買，也不刪掉觀察／避開樣本'};
 });
}
export async function confirmBatch(rows,ctx,settings,existing=[],wallNow=new Date()){
 wallNow=new Date(wallNow);if(!Number.isFinite(+wallNow))throw Error('無效確認時間');
 const identity=await P.sha({sourceHash:ctx.hash,settings:P.settings({...DEFAULT,...settings}),engine:VERSION});
 if(existing.some(b=>b.identity===identity))throw Error('同快照與設定已確認過；請開既有批次，不重複計入');
 const frozen=[];
 for(const row of rows){const p=P.copy(row.proposal),hash=await P.sha(p);let account=null;
  if(row.eligible){account=P.newExperiment(p.settings,ctx);account.name='開發者 / '+row.symbol;account=P.approve(account,p,hash,wallNow);}
  frozen.push({...P.copy(row),planHash:hash,account,lastError:null});
 }
 const batch={schema:'dev1932-batch-1',version:VERSION,id:crypto.randomUUID(),identity,createdAt:wallNow.toISOString(),context:P.copy(ctx),settings:P.settings({...DEFAULT,...settings}),rows:frozen,revision:1,events:[{seq:1,type:'batch_confirmed',at:wallNow.toISOString(),identity}],deletedAt:null,
  accounting:'independent_accounts_not_shared_capital',baselineNotOriginalAdvice:true};
 return batch;
}
export function status(row){
 if(!row.account)return '未建試單（仍驗證）';
 const a=row.account;if(a.position)return '持有中';if(a.closed.length)return '已完成';
 const o=a.orders.at(-1);return ({pending:'待日K判定',unfilled:'限價等條件未成交',uncertain:'成交不確定',expired:'已過期',cancelled:'已取消'})[o?.status]||'已結算';
}
export async function advanceBatch(batch,market,cal,wallNow=new Date(),maxSessions=30){
 wallNow=new Date(wallNow);if(!Number.isFinite(+wallNow))throw Error('無效結算時間');
 if(batch.deletedAt)throw Error('批次已移到回收桶');const b=P.copy(batch);let changed=0;
 for(const row of b.rows){if(!row.account)continue;row.lastError=null;
  for(let k=0;k<maxSessions;k++){
   const a=row.account;
   if(!a.position&&!a.orders.some(o=>o.status==='pending')&&!a.receivables.length)break;
   let need;try{need=P.settlementNeeds(a,cal,wallNow)}catch(e){row.lastError=e.message;break}
   if(['not_closed','calendar_missing','deleted'].includes(need.state)){row.lastError=need.message;break}
   let bars={},failed=false;
   for(const sy of need.symbols){const payload=market[sy];const diag=P.diagnoseMarket(payload,sy,need.date,`data/market/${sy.replaceAll('.','_')}.json`);if(!diag.ok){row.lastError=diag.message;failed=true;break}bars[sy]=diag.bar;}
   if(failed)break;
   try{const next=P.advance(a,need.date,bars,cal,wallNow);next.events.at(-1).payload.barHashes=await P.sha(bars);P.validateRun(next);row.account=next;changed++;}catch(e){row.lastError=e.message;break;}
  }
 }
 b.revision++;b.events.push({seq:b.revision,type:'batch_settlement',at:wallNow.toISOString(),sessions:changed});return b;
}
export function batchSummary(b){const active=b.rows.filter(r=>r.account),done=active.filter(r=>r.account.closed.length),balances=active.map(r=>P.balance(r.account));return {
 observed:b.rows.length,eligible:active.length,blocked:b.rows.length-active.length,pending:active.filter(r=>r.account.orders.some(o=>o.status==='pending')).length,
 holding:active.filter(r=>r.account.position).length,completed:done.length,
 meanIndependentReturnPct:balances.length?P.m(balances.reduce((a,x)=>a+x.returnPct,0)/balances.length):null,
 completedWinRate:done.length?P.m(done.filter(r=>P.balance(r.account).realized>0).length/done.length*100):null,
 errors:b.rows.filter(r=>r.lastError).length,notPortfolio:true};}
export async function validateBatch(b){
 if(b?.schema!=='dev1932-batch-1'||!Array.isArray(b.rows)||!b.id||!b.context||b.rows.length>100)throw Error('不是開發者批次格式');P.settings(b.settings);
 if(!Array.isArray(b.events)||b.events.length!==b.revision||b.events.some((e,i)=>e.seq!==i+1))throw Error('批次事件順序錯誤');
 const expected=await P.sha({sourceHash:b.context.hash,settings:b.settings,engine:VERSION});if(expected!==b.identity)throw Error('批次設定／來源已更動');
 const seen=new Set;
 for(const r of b.rows){if(seen.has(r.symbol))throw Error('重複標的');seen.add(r.symbol);if(await P.sha(r.proposal)!==r.planHash)throw Error('計畫已被改寫');if(r.proposal.symbol!==r.symbol)throw Error('標的不符');if(r.account){P.validateRun(r.account);for(const o of r.account.orders)if(o.side==='buy'&&o.hash!==r.planHash)throw Error('試單雜湊不符');}}
 return true;
}
export function trash(b,deleted=true){const c=P.copy(b);c.deletedAt=deleted?new Date().toISOString():null;c.revision++;c.events.push({seq:c.revision,type:deleted?'trash':'restore',at:new Date().toISOString()});return c;}
