/** StockLab18 pure planning + actual-fill bookkeeping. NO brokerage integration. */
import {ledger as scenarioLedger,sizePosition} from './risk17.mjs';
export const VERSION='18.0.0';
export const DEFAULT_PROFILE={salary:39000,monthly:4000,available:4000,budget:4000,loss:200,hold:10,goal:150,reserve:false,feeRate:.001425,minFee:20,slippage:.001};
export const money=n=>Math.round((n+Number.EPSILON)*100)/100;
export function profile(p={}){p={...DEFAULT_PROFILE,...p};for(const k of ['salary','monthly','available','budget','loss','hold','goal','feeRate','minFee','slippage']){if(!Number.isFinite(p[k]))throw Error('請填有效數字：'+k)}if(p.salary<0||p.monthly<0||p.monthly>p.salary||p.available<0||p.budget<=0||p.loss<=0||p.goal<0)throw Error('預算需大於0；每月投入不可超過薪資');if(!Number.isInteger(p.hold)||p.hold<1||p.hold>60)throw Error('持有期間限1到60個交易日');if(p.feeRate<0||p.feeRate>.02||p.minFee<0||p.slippage<0||p.slippage>.05)throw Error('費用參數不合理');return p}
export function taipeiDay(at=new Date()){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(at)}
function addDay(s,n=1){let d=new Date(s+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)}
export function isSession(day,cal){let w=new Date(day+'T12:00:00Z').getUTCDay();return w!==0&&w!==6&&!cal.closed.includes(day)}
export function covered(day,cal){return !!cal&&day>=cal.start&&day<=cal.end}
export function expectedClose(at,cal){const dt=new Date(at);let day=taipeiDay(dt);let hr=Number(new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'Asia/Taipei'}).format(dt).replace(':',''));if(hr<1330)day=addDay(day,-1);for(let i=0;i<32;i++,day=addDay(day,-1))if(isSession(day,cal))return day;throw Error('日曆缺資料')}
export function addSessions(day,n,cal){if(!covered(day,cal))throw Error('交易日曆未涵蓋此日期，不能推算交割');let d=day;for(let i=0;i<n;){d=addDay(d);if(!covered(d,cal))throw Error('需更新次年度日曆');if(isSession(d,cal))i++}return d}
export function sessionCount(start,end,cal){let n=0;for(let d=start;d<=end;d=addDay(d)){if(!covered(d,cal))return null;if(isSession(d,cal))n++}return n}
const tick=p=>p<10?.01:p<50?.05:p<100?.1:p<500?.5:p<1000?1:5;
const floorTick=p=>money(Math.floor((p+1e-8)/tick(p))*tick(p));
function ceilTick(p){return money(Math.ceil((p-1e-8)/tick(p))*tick(p))}
function forecastPrice(q,entry,profit,a,etf){let lo=entry,hi=entry*10+100;for(let i=0;i<64;i++){let m=(lo+hi)/2;if(scenarioLedger(q,entry,m,a,etf).pnl>=profit)hi=m;else lo=m}return ceilTick(hi)}
export function plan(stock,p0,context,now=new Date(),account=null){
 const p=profile(p0),bars=stock.candles||[],b=bars.at(-1)||{},cal=context.calendar,blocks=[],warnings=[];
 let expected=expectedClose(now,cal);if(!covered(taipeiDay(now),cal)||!covered(expected,cal))blocks.push('年度交易日曆未核對，暫不產生買進股數');
 if(b.date!==expected)blocks.push(`價格過期：應有 ${expected} 收盤，實際 ${b.date||'缺值'}`);
 const ver=stock.quote_verification||{};if(ver.status!=='matched'||ver.official?.date!==b.date||!Number.isFinite(ver.official?.close)||Math.abs(ver.official.close-b.close)>Math.max(.001,b.close*.00001))blocks.push('此價格尚未與同日交易所收盤核對');
 if(context.demo)blocks.push('示範資料不可用於買進');
 if(!p.reserve)blocks.push('先確認這筆錢不影響生活與緊急預備金');
 const dec=stock.decision||{};if(['avoid','insufficient'].includes(dec.code))blocks.push('原判斷資料不足或風險偏高');
 if((dec.score||0)<55)blocks.push('研究分未達55（規則門檻，不是機率）');
 if(stock.symbol.startsWith('00'))blocks.push('ETF需檢查折溢價與追蹤差異，本版不套個股買進條件');
 if(stock.news?.some(e=>e.included&&e.impact_score<=-30))blocks.push('存在重大負向事件，先核對新證據');
 if(account&&account.holdings.some(h=>h.quantity>0))blocks.push('已有持股，穩健預設同時只持有1檔；先管理原部位');
 let cap=Math.min(p.available,p.budget,account?account.spendableCash:p.available),risk=Math.min(p.loss,cap*.05);
 const result={version:VERSION,symbol:stock.symbol,name:stock.name,sourceDate:b.date,createdAt:now.toISOString(),sourceHash:context.source_snapshot_sha256,settings:{...p},blocks,warnings,recommendedShares:0,conditionalShares:0,expectedReturn:null,expectedReturnNote:'沒有前瞻驗證，不能給可信預期報酬；下列僅價位情境',holdDays:p.hold,reviewDays:Math.min(5,p.hold),goal:p.goal,budget:cap,plannedRiskBudget:risk,originalLabel:dec.label};
 if(![b.close,b.atr,b.resistance,b.ma20,b.ma60].every(x=>Number.isFinite(x)&&x>0)){blocks.push('日K、均線或ATR不足');return result}
 if(b.close<=b.ma20||b.close<=b.ma60)blocks.push('現價未同時站上月線與季線');
 const stop=floorTick(b.close-2*b.atr),pressure=floorTick(b.resistance);if(stop<=0||pressure<=stop||cap<=0){blocks.push('預算或停損價位無效');return result}
 const a={equity:Math.max(cap,1),available_cash:Math.max(cap,0),risk_fraction:Math.max(.000001,Math.min(1,risk/Math.max(cap,1))),position_fraction:1,gross_fraction:1,portfolio_risk_fraction:Math.max(.000001,Math.min(1,risk/Math.max(cap,1))),sector_fraction:1,min_commission:p.minFee,commission_rate:p.feeRate,slippage:p.slippage,min_reward_risk:1.5,holding_sessions:p.hold,max_positions:1,lot_size:1,holdings:[]};
 let entry=floorTick(Math.min(b.close,(pressure+1.5*stop)/2.5)),z={quantity:0};
 for(let i=0;i<800&&entry>stop;i++){
  z=sizePosition(entry,stop,pressure,a,false,stock.sector);
  if(z.quantity>0&&z.net_reward_risk>=1.5){const goalP=forecastPrice(z.quantity,entry,p.goal,a,false),t=p.goal>0?Math.min(goalP,pressure):pressure;const loss=scenarioLedger(z.quantity,entry,stop,a,false).pnl,win=scenarioLedger(z.quantity,entry,t,a,false).pnl;if(win/Math.max(.01,-loss)>=1.5)break;}
  entry=floorTick(entry-tick(entry));
 }
 if(!z.quantity||entry<=stop){blocks.push('資金／風險／最低手續費限制，無合適股數');return {...result,stop,pressure,entry}}
 const wanted=forecastPrice(z.quantity,entry,p.goal,a,false),target=p.goal>0?Math.min(wanted,pressure):pressure;
 const worst=scenarioLedger(z.quantity,entry,stop,a,false),best=scenarioLedger(z.quantity,entry,target,a,false),flat=scenarioLedger(z.quantity,entry,entry,a,false),rr=best.pnl/Math.max(.01,-worst.pnl);
 if(entry<Math.max(b.ma20,b.ma60))blocks.push('可接受價低於趨勢線；不是叫你掛單抄底，需等新資料');
 if(rr<1.5)blocks.push('目標扣成本後不足以補償1.5倍風險，不為了成交放寬停損');
 if(wanted>pressure)warnings.push(`想賺 ${p.goal} 元須約 ${wanted} 元；超過近期壓力 ${pressure}，不假裝目標可達成`);
 if(cap<p.budget)warnings.push('可用資金不足原預算，已縮小股數');
 if(p.loss>risk)warnings.push(`本次最多規劃損失 ${risk.toFixed(0)} 元（不超過投入預算5%）`);
 warnings.push('僅依收盤計畫：券商現價須落在價帶；跳空、鎖漲跌停或滑價可能超過預計損失');
 let expiry,plannedEndDate,plannedReviewDate;try{expiry=addSessions(b.date,1,cal);plannedEndDate=addSessions(expiry,p.hold-1,cal);plannedReviewDate=addSessions(expiry,Math.min(5,p.hold)-1,cal)}catch(e){blocks.push(e.message)}
 if(expiry&&taipeiDay(now)>expiry)blocks.push('這張價位計畫已過下一交易日，必須重算');
 return {...result,entry,entryLow:ceilTick(Math.max(stop+tick(entry),entry-.25*b.atr)),stop,pressure,target,goalPrice:wanted,goalFeasible:wanted<=pressure,conditionalShares:z.quantity,recommendedShares:blocks.length?0:z.quantity,cashCost:worst.buy_cash,stopPnl:worst.pnl,flatPnl:flat.pnl,targetPnl:best.pnl,targetReturn:best.return_pct,riskReward:money(rr),expiry,plannedEndDate,plannedReviewDate,forecastRangeLabel:'情境，非預測',state:blocks.length?'wait':'conditional'};
}
export function defaultAccount(){return {schema:1,events:[],plans:[],createdAt:new Date().toISOString()}}
export function validateEvent(e){if(!e||typeof e.id!=='string'||!e.id||!/^\d{4}-\d{2}-\d{2}$/.test(e.date)||!Number.isFinite(Date.parse(e.date+'T00:00:00Z'))||new Date(e.date+'T00:00:00Z').toISOString().slice(0,10)!==e.date)throw Error('紀錄缺ID或有效日期');if(typeof e.recordedAt!=='string'||!Number.isFinite(Date.parse(e.recordedAt)))throw Error('紀錄缺有效儲存時間');if(!['deposit','withdraw','buy','sell','dividend','void'].includes(e.type))throw Error('未知交易種類');if(['buy','sell'].includes(e.type)){if(!/^\d{4,6}[AB]?\.(TW|TWO)$/.test(e.symbol||''))throw Error('請選正確股票代號');if(!Number.isInteger(e.quantity)||e.quantity<=0||!Number.isFinite(e.price)||e.price<=0)throw Error('股數為正整數、價格須大於0');if(!Number.isFinite(e.fee)||e.fee<0||!Number.isFinite(e.tax)||e.tax<0)throw Error('費用與稅需為非負值');if(e.quantity>100000000||e.price>10000000)throw Error('成交數量或價格超出個人版合理範圍');if(e.type==='buy'&&e.tax!==0)throw Error('買入不計證交稅')}if(['deposit','withdraw','dividend'].includes(e.type)&&(!Number.isFinite(e.amount)||e.amount<=0))throw Error('金額必須大於0');if(e.type==='void'&&!e.target)throw Error('需指定作廢對象');return true}
export function accountState(events,quotes={},cal,until=taipeiDay()){
 let cash=0,contributions=0,withdrawals=0,dividends=0,realized=0,receivables=[],lots={},closed=[],activePlans={};
 const ids=new Set;for(const e of events){validateEvent(e);if(ids.has(e.id))throw Error('重複ID');ids.add(e.id)}
 for(const e of events.filter(x=>x.type==='void')){const target=events.find(t=>t.id===e.target);if(!target||target.type==='void'||target.id===e.id)throw Error('作廢對象不存在或不能作廢更正紀錄')}
 const applicable=events.filter(e=>e.date<=until);const removed=new Set(applicable.filter(e=>e.type==='void').map(e=>e.target));
 const sorted=applicable.filter(e=>e.type!=='void'&&!removed.has(e.id)).sort((a,b)=>a.date.localeCompare(b.date)||a.recordedAt.localeCompare(b.recordedAt));
 for(const e of sorted){
  for(const r of receivables.slice())if(r.date<=e.date){cash=money(cash+r.amount);receivables.splice(receivables.indexOf(r),1)}
  if(e.type==='deposit'){cash=money(cash+e.amount);contributions=money(contributions+e.amount);continue}
  if(e.type==='withdraw'){if(e.amount>cash+.005)throw Error('提款超過可用現金（不含待交割）');cash=money(cash-e.amount);withdrawals=money(withdrawals+e.amount);continue}
  if(e.type==='dividend'){cash=money(cash+e.amount);dividends=money(dividends+e.amount);continue}
  if(!isSession(e.date,cal)||!covered(e.date,cal))throw Error('成交日期為休市日或日曆未涵蓋');
  if(e.type==='buy'){
   const cost=money(e.quantity*e.price+e.fee);if(cost>cash+.005)throw Error('成交支出超過已入帳資金；先記錄投入款或更正成交數字');cash=money(cash-cost);(lots[e.symbol]??=[]).push({quantity:e.quantity,cost,date:e.date,price:e.price,id:e.id,planId:e.planId,name:e.name});continue;
  }
  let position=lots[e.symbol]||[],held=position.reduce((s,l)=>s+l.quantity,0);if(e.quantity>held)throw Error('賣出股數超過當時持股');
  let remaining=e.quantity,cost=0,entries=[],planIds=[];
  for(const l of position){if(!remaining)break;const q=Math.min(remaining,l.quantity);let c=q===l.quantity?l.cost:money(l.cost*q/l.quantity);cost=money(cost+c);l.cost=money(l.cost-c);l.quantity-=q;remaining-=q;entries.push(l.date);if(l.planId)planIds.push(l.planId)}
  const proceeds=money(e.quantity*e.price-e.fee-e.tax),pnl=money(proceeds-cost);realized=money(realized+pnl);const settlement=e.settlement||addSessions(e.date,2,cal);
  if(settlement<addSessions(e.date,2,cal)||!isSession(settlement,cal))throw Error('交割日不可早於T+2或為休市日');receivables.push({date:settlement,amount:proceeds});
  closed.push({...e,cost,proceeds,pnl,returnPct:cost?money(pnl/cost*100):null,entryDates:entries,planIds:[...new Set(planIds)],settlement});
 }
 for(const r of receivables.slice())if(r.date<=until){cash=money(cash+r.amount);receivables.splice(receivables.indexOf(r),1)}
 const holdings=[];let marketValue=0,unrealized=0,allPriced=true;
 for(const [symbol,ls] of Object.entries(lots)){
  const alive=ls.filter(l=>l.quantity>0),quantity=alive.reduce((s,l)=>s+l.quantity,0);if(!quantity)continue;
  const cost=money(alive.reduce((s,l)=>s+l.cost,0)),rawQuote=quotes[symbol],actionPending=rawQuote?.corporateActionDates?.some(d=>d>=alive[0].date&&d<=until),quote=rawQuote&&Number.isFinite(rawQuote.close)&&rawQuote.close>0&&!actionPending&&rawQuote.date>=alive.at(-1).date&&rawQuote.date<=until?rawQuote:null;let mark=quote?.close??null;
  if(mark===null){allPriced=false;mark=cost/quantity}
  const value=money(mark*quantity);marketValue=money(marketValue+value);unrealized=money(unrealized+value-cost);
  holdings.push({symbol,name:alive[0].name||symbol,quantity,cost,averageCost:cost/quantity,marketValue:value,unrealizedPnl:money(value-cost),quoteDate:quote?.date||null,quoteMissing:!quote,corporateActionPending:!!actionPending,firstEntry:alive[0].date,lots:alive});
 }
 const unsettled=money(receivables.reduce((s,r)=>s+r.amount,0)),equity=money(cash+unsettled+marketValue),netContribution=money(contributions-withdrawals),pnl=money(equity-netContribution);
 return {spendableCash:cash,unsettled,receivables,contributions,withdrawals,netContribution,dividends,realizedPnl:realized,unrealizedPnl:unrealized,holdings,closed,equity,totalPnl:pnl,returnOnDeposits:contributions?money(pnl/contributions*100):null,allPriced,hasRecords:sorted.length>0};
}
export function appendEvent(account,e,quotes,cal,today=taipeiDay()){
 validateEvent(e);if(e.date>today)throw Error('不能記錄未來成交');const next={...account,events:[...account.events,e]};accountState(next.events,quotes,cal,today);return next
}
export function defaultFees(type,quantity,price,p,etf=false){const gross=quantity*price;return {fee:money(Math.max(p.minFee,gross*p.feeRate)),tax:type==='sell'?money(gross*(etf?.001:.003)):0}}
export function cashIdentity(s){return Math.abs((s.realizedPnl+s.unrealizedPnl+s.dividends)-s.totalPnl)<.05}
export function drawdown(points){let peak=0,dd=0;for(const v of points){peak=Math.max(peak,v);if(peak>0)dd=Math.min(dd,(v/peak-1)*100)}return money(dd)}

export function personalTimeline(events,stocks,cal,until=taipeiDay()) {
 const dated=events.filter(e=>e.date<=until);if(!dated.length)return [];
 const start=dated.map(e=>e.date).sort()[0];const keys=new Set([start,until,...dated.map(e=>e.date)]);
 for(const s of stocks)for(const b of s.candles||[])if(b.date>=start&&b.date<=until)keys.add(b.date);
 return [...keys].sort().slice(-800).map(day=>{const q=Object.fromEntries(stocks.map(s=>{let bars=(s.candles||[]).filter(b=>b.date<=day);return [s.symbol,{...(bars.at(-1)||{}),corporateActionDates:bars.filter(b=>b.corporate_action).map(b=>b.date)}]}));const s=accountState(events,q,cal,day);return {date:day,value:s.totalPnl,equity:s.equity,contributions:s.contributions,realized:s.realizedPnl,priced:s.allPriced};});
}
