/** Reprice ONLY unconfirmed latest plans. Original forecast and historical replay stay intact. */
import * as P from './paper-engine.mjs';
export async function previewPrices(snapshot,ctx,payloads){
 const copy=P.copy(snapshot),evidence={};if(ctx.mode!=='forward')return {snapshot:copy,evidence};
 const at=new Date(ctx.at),day=P.dayAt(at),hhmm=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(at).replace(':',''));
 for(const stock of copy.stocks){
  const payload=payloads[stock.symbol];if(!Array.isArray(payload?.candles)||payload.demo||payload.symbol&&payload.symbol!==stock.symbol)continue;
  const rows=payload.candles.filter(b=>P.dateValid(b.date)&&b.date<=day&&(b.date<day||hhmm>=1330)&&b.is_final!==false&&!b.provisional).sort((a,b)=>a.date.localeCompare(b.date));
  if(!rows.length)continue;
  const original=stock.candles?.at(-1)?.date;
  if(original&&rows.at(-1).date<=original)continue;
  const last=rows.at(-1);
  // Preserve suspicious latest rows for the proposal validator to reject; never substitute an old safe price.
  stock.candles=rows;
  evidence[stock.symbol]={path:`data/market/${stock.symbol.replaceAll('.','_')}.json`,candles_sha256:await P.sha(rows),quote_date:last.date,
   original_quote_date:original||null,original_analysis_at:snapshot.generated_at,
   note:'只以新完整日K重算尚未確認的價帶／股數；新聞、原標籤與分數仍來自原分析，非重做六面向。'};
 }
 return {snapshot:copy,evidence};
}
