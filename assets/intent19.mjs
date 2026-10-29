/** Explicit execution dates. A data outage is not a bearish market opinion. */
import {plan,taipeiDay,isSession,covered,addSessions,expectedClose} from './life-engine.mjs?v=19';
export const INTENT_VERSION='19.0.0';
export function clockTaipei(now=new Date()){
 const day=taipeiDay(now);const hhmm=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(now).replace(':',''));
 return {day,hhmm};
}
export function intentTiming(intent,calendar,now=new Date()){
 const {day,hhmm}=clockTaipei(now),mode=intent==='tomorrow'?'tomorrow':'today';
 if(!covered(day,calendar))return {mode,day,phase:'calendar_unknown',issues:['交易日曆未涵蓋今天；請更新年度日曆'],targetDate:null};
 const trading=isSession(day,calendar);
 try{
  if(mode==='today'){
   if(!trading)return {mode,day,phase:'closed',issues:[],targetDate:null,nextDate:addSessions(day,1,calendar),message:'今天休市，請查看下一交易日計畫'};
   if(hhmm>=1330)return {mode,day,phase:'closed',issues:[],targetDate:day,nextDate:addSessions(day,1,calendar),message:'今日已收盤；不是看空，請查看下一交易日計畫'};
   return {mode,day,phase:hhmm<900?'premarket':'market',targetDate:day,requiredClose:expectedClose(new Date(day+'T08:00:00+08:00'),calendar),issues:[]};
  }
  const targetDate=addSessions(day,1,calendar);
  const requiredClose=trading?day:expectedClose(now,calendar);
  return {mode,day,targetDate,requiredClose,phase:trading&&hhmm<1800?'await_evening':'next_session',issues:[]};
 }catch(e){return {mode,day,phase:'calendar_unknown',targetDate:null,issues:[e.message]};}
}
export function classifyBlock(text){
 if(/價格過期|收盤核對|年度交易日曆|日曆|示範資料|日K、均線|計畫已過|準備|新聞更新|未來|處理|原始時間/.test(text))return 'data';
 if(/生活|預備金|已有持股|預算|資金|股數|手續費/.test(text))return 'account';
 if(/價低於|不追|趨勢線|報酬|1.5倍|目標扣/.test(text))return 'price';
 return 'research';
}
export function makeIntent(stock,settings,context,intent='today',now=new Date(),account=null){
 const timing=intentTiming(intent,context.calendar,now);
 let ticket=plan(stock,settings,{...context,executionTiming:timing},now,account);
 ticket={...ticket,intent:timing.mode,timing,analysisAt:context.generated_at,asOf:context.as_of};
 const extra=[];const generated=new Date(context.generated_at);
 if(!Number.isFinite(generated.getTime()))extra.push('缺少原始時間：無法核對分析何時完成');
 else if(generated.getTime()>now.getTime()+60000)extra.push('原始時間在未來，停止使用這份分析');
 else if(timing.phase!=='closed'&&timing.requiredClose){
  const gc=clockTaipei(generated);
  if(gc.day<timing.requiredClose||(gc.day===timing.requiredClose&&gc.hhmm<1800))extra.push('晚間新聞更新未完成：需要參考收盤日18:00後產生的分析');
  if((now-generated)>36*3600*1000)extra.push('新聞更新落後超過36小時：需重新抓取，不是看空');
 }
 if(timing.phase==='await_evening')extra.push('下一交易日準備中：待當日收盤與18:00後新聞分析完成');
 extra.push(...timing.issues);
 ticket.blocks=[...new Set([...ticket.blocks,...extra])];
 ticket.groups={data:[],account:[],price:[],research:[]};
 for(const reason of ticket.blocks)ticket.groups[classifyBlock(reason)].push(reason);
 let status;
 if(timing.phase==='closed')status='closed';
 else if(ticket.groups.data.length)status='data_pending';
 else if(ticket.groups.research.length)status='avoid';
 else if(ticket.groups.account.length)status='setup';
 else if(ticket.groups.price.length)status='price_wait';
 else if(ticket.conditionalShares>0)status='conditional_buy';
 else status='no_plan';
 const labels={closed:'今日休市／收盤',data_pending:'資料待修復，不是看空',avoid:'本檔條件未達，暫不進場',setup:'先完成資金或持股確認',price_wait:'等價位，非立即追價',conditional_buy:'價帶內可考慮買入',no_plan:'沒有可用計畫'};
 const actions={closed:'切換下一交易日計畫',data_pending:'查看更新狀態與修復步驟',avoid:'查看未達條件，不為了成交放寬規則',setup:'完成上方首次使用引導',price_wait:'不追價；跌破趨勢的舊計畫須重算',conditional_buy:'核對券商即時價與新消息 → 保存計畫 → 券商限價委託',no_plan:'查看資料或資金限制'};
 const group=status==='data_pending'?'data':status==='setup'?'account':status==='price_wait'?'price':'research';
 return {...ticket,status,statusLabel:labels[status],action:actions[status],primaryReason:status==='closed'?timing.message:(ticket.groups[group][0]||ticket.warnings?.[0]||'只在有效價帶內考慮，不保證成交或獲利'),recommendedShares:status==='conditional_buy'?ticket.conditionalShares:0};
}
export function chooseIntent(stocks,settings,context,intent,now,account){
 const rank={conditional_buy:0,price_wait:1,setup:2,avoid:3,data_pending:4,closed:5,no_plan:6};
 return stocks.map(stock=>({stock,ticket:makeIntent(stock,settings,context,intent,now,account)})).sort((a,b)=>(rank[a.ticket.status]-rank[b.ticket.status])||((b.ticket.riskReward||0)-(a.ticket.riskReward||0))||((b.stock.decision?.score||0)-(a.stock.decision?.score||0)));
}
export function brokerNote(ticket){
 if(ticket.status!=='conditional_buy')throw Error('此計畫尚未通過；不能複製成可買委託');
 return ['StockLab 19 條件式研究委託（不自動下單）',`${ticket.name} ${ticket.symbol}`,`有效日：${ticket.expiry}`,`限價：${ticket.entryLow}～${ticket.entry} 元；高於上限不追`,`${ticket.conditionalShares} 股；預算約 ${ticket.cashCost} 元`, `停損參考 ${ticket.stop} 元；跳空可能超過 ${Math.abs(ticket.stopPnl)} 元規劃損失`, `退出情境 ${ticket.target} 元（非預測），若成交約 ${ticket.targetPnl} 元`, `持有最多 ${ticket.holdDays} 個交易日；${ticket.plannedReviewDate} 複查；${ticket.plannedEndDate} 退出檢查`, `資料截至 ${ticket.sourceDate} 收盤；先核對券商現價及隔夜新消息`].join('\n');
}
