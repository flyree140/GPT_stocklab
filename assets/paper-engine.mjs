/** StockLab PaperLab — closed experiment only; zero broker endpoints.
 * Decisions are frozen before replay. Money is rounded to cents, not legal
 * brokerage rounding. Day-OHLC executions are explicit approximations.
 */
export const LAB_VERSION='19.1-paper.1';
export const DEFAULTS=Object.freeze({capital:4000,budget:4000,maxLoss:200,goal:150,hold:10,feeRate:0.001425,minFee:20,slip:0.001,strategy:'candidate',autoExit:true,autoFollow:true});
export const m=n=>Math.round((n+Number.EPSILON)*100)/100;
export const copy=x=>structuredClone(x);
export const dayAt=t=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(t));
export function canonical(x){if(x===null)return 'null';if(typeof x==='number'){if(!Number.isFinite(x))throw Error('無效數字');return JSON.stringify(x)}if(Array.isArray(x))return '['+x.map(canonical).join(',')+']';if(typeof x==='object')return '{'+Object.keys(x).filter(k=>x[k]!==undefined).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}';return JSON.stringify(x)}
export async function sha(x){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(typeof x==='string'?x:canonical(x))))].map(v=>v.toString(16).padStart(2,'0')).join('')}
export function dateValid(d){return /^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d+'T12:00:00Z'))&&new Date(d+'T12:00:00Z').toISOString().slice(0,10)===d}
function add(d,n){const t=new Date(d+'T12:00:00Z');t.setUTCDate(t.getUTCDate()+n);return t.toISOString().slice(0,10)}
export function session(d,cal){if(!dateValid(d)||!cal||d<cal.start||d>cal.end)throw Error('交易日曆未涵蓋 '+d);return ![0,6].includes(new Date(d+'T12:00:00Z').getUTCDay())&&!cal.closed.includes(d)}
export function nextSession(d,cal,n=1){let t=d;for(let i=0;i<n;){t=add(t,1);if(session(t,cal))i++}return t}
export function decisionSession(at,cal){const d=dayAt(at),hhmm=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(at)).replace(':',''));return session(d,cal)&&hhmm<900?d:nextSession(d,cal)}
export function settings(p={}){p={...DEFAULTS,...p};for(const k of ['capital','budget','maxLoss','goal','hold','feeRate','minFee','slip'])if(!Number.isFinite(p[k]))throw Error('請填有效數字：'+k);if(p.capital<=0||p.budget<=0||p.maxLoss<=0||p.goal<0||p.maxLoss>p.capital||!Number.isInteger(p.hold)||p.hold<1||p.hold>120)throw Error('資金／期限不合理');if(p.feeRate<0||p.feeRate>.02||p.minFee<0||p.minFee>1000||p.slip<0||p.slip>.05)throw Error('費用不合理');if(!['candidate','original'].includes(p.strategy))throw Error('未知試驗規則');p.autoExit=!!p.autoExit;p.autoFollow=!!p.autoFollow;return p}
export function checkBar(b,d){if(!b||b.date!==d)throw Error(d+' 缺少行情，不以其他日期代替');for(const k of ['open','high','low','close','volume'])if(!Number.isFinite(b[k]))throw Error(d+' '+k+' 不是數字');if(Math.min(b.open,b.high,b.low,b.close)<=0||b.low>Math.min(b.open,b.close)||b.high<Math.max(b.open,b.close)||b.low>b.high||b.volume<=0)throw Error(d+' 行情價量不合法');if(b.corporate_action)throw Error(d+' 有除權息／拆股標記；暫停，不當成價格漲跌');return b}
export function fee(q,p,s){return m(Math.max(s.minFee,q*p*s.feeRate))}
export function scenario(q,entry,exit,s,tax=.003){const buy=m(q*entry+fee(q,entry,s)),sellPrice=m(exit*(1-s.slip)),gross=m(q*sellPrice),sellFee=fee(q,sellPrice,s),sellTax=m(gross*tax),proceeds=m(gross-sellFee-sellTax);return {buy,exit:sellPrice,fee:fee(q,entry,s)+sellFee,tax:sellTax,proceeds,pnl:m(proceeds-buy),pct:m((proceeds-buy)/buy*100)}}
export function size(limit,stop,s,cash){const cap=Math.min(cash,s.budget),risk=Math.min(s.maxLoss,cap),tax=s.tax??.003;let lo=0,hi=Math.min(1000000,Math.floor(cap/limit));while(lo<hi){const q=Math.ceil((lo+hi)/2),r=scenario(q,limit,stop,s,tax);if(r.buy<=cap&&-r.pnl<=risk)lo=q;else hi=q-1}return lo}
function goalPrice(q,entry,s,tax){let lo=entry,hi=entry*10;for(let i=0;i<64;i++){const v=(lo+hi)/2;if(scenario(q,entry,v,s,tax).pnl>=s.goal)hi=v;else lo=v}return Math.ceil(hi*100)/100}
function lastClosedDay(at,cal){let d=dayAt(at);const h=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(at)).replace(':',''));if(h<1330)d=add(d,-1);for(let i=0;i<20;i++,d=add(d,-1)){if(session(d,cal))return d}throw Error('找不到上一交易日')}
/** Proposal never inspects future market files. No live-budget/reserve check. */
export function propose(stock,s0,ctx,account=null){
 const s=settings(s0),p={version:LAB_VERSION,symbol:stock.symbol,name:stock.name,sector:stock.sector,sourcePath:ctx.path,sourceHash:ctx.hash,sourceGeneratedAt:ctx.generatedAt,asOf:ctx.asOf,decisionAt:ctx.at,dataMode:ctx.mode,settings:copy(s),original:copy(stock.decision||{}),blocks:[],warnings:[],analysis:[],expectedReturn:null,reasonForNoForecast:'尚未以未見資料校準，不把目標或研究分當成預期報酬／機率',quantity:0,tax:stock.sector==='ETF'||stock.type==='etf'?.001:.003};
 if(!Number.isFinite(Date.parse(ctx.at)))throw Error('缺少分析時點');if(new Date(ctx.generatedAt)>new Date(ctx.at))p.blocks.push('來源在試驗時點之後才產生，不能倒填');
 const maxDay=lastClosedDay(ctx.at,ctx.cal);const bars=(stock.candles||[]).filter(b=>b.date<=ctx.asOf&&b.date<=maxDay).sort((a,b)=>a.date.localeCompare(b.date));const b=bars.at(-1),dec=p.original;
 p.referenceDate=b?.date;p.referencePrice=b?.close;p.cutoff=ctx.at;p.validFor=decisionSession(ctx.at,ctx.cal);p.deadline=nextSession(p.validFor,ctx.cal,s.hold-1);p.reviewDate=nextSession(p.validFor,ctx.cal,Math.min(5,s.hold)-1);
 if(!b){p.blocks.push('截止時點前沒有可用日K');return p}try{checkBar(b,b.date)}catch(e){p.blocks.push(e.message);return p}
 if(b.date!==maxDay)p.blocks.push(`行情缺日：當時應有 ${maxDay}，只有 ${b.date}；可改選資料完整的歷史日`);
 if(account&&(account.position||account.orders?.some(o=>o.status==='pending')))p.blocks.push('此試驗同時只持有一筆，已有部位或待成交試單');
 if(ctx.mode==='demo')p.warnings.push('純合成教學資料，不納入真實樣本績效');else if(ctx.mode!=='forward')p.warnings.push('歷史檔案重播，不是前瞻實績；來源報價未獨立核實');
 p.warnings.push('未做交易所逐價核對：在封閉試驗中列為資料品質警示，不要求實盤授權');
 if(s.strategy==='original'&&dec.code!=='conditional_buy')p.blocks.push('忠實原建議組：原標籤不是條件式買入');
 if(s.strategy==='candidate'&&(!Number.isFinite(dec.score)||dec.score<50||dec.code==='avoid'))p.blocks.push('候選試買組：需原分數≥50且不是避開；此為固定研究規則，非最佳化績效');
 if(![b.atr,b.resistance].every(n=>Number.isFinite(n)&&n>0)){p.blocks.push('缺ATR或近期壓力，不能用預設百分比冒充個股分析');return p}
 const supportStop=dec.plan?.stop_reference,stop=Number.isFinite(supportStop)&&supportStop>0&&supportStop<b.close?supportStop:b.close-2*b.atr;
 p.stop=m(stop);p.pressure=m(b.resistance);p.limit=m(b.close);if(p.stop<=0||p.stop>=p.limit||p.pressure<=p.limit){p.blocks.push('停止價或上方參考空間無效');return p}
 p.quantity=size(p.limit,p.stop,{...s,tax:p.tax},account?.cash??s.capital);
 if(p.quantity<=0){p.blocks.push('資金與損失預算不容許一股及成本');return p}
 p.wanted=goalPrice(p.quantity,p.limit,s,p.tax);p.target=m(Math.min(p.pressure,s.goal>0?p.wanted:p.pressure));p.goalFeasible=s.goal===0||p.wanted<=p.pressure;
 p.downside=scenario(p.quantity,p.limit,p.stop,s,p.tax);p.upside=scenario(p.quantity,p.limit,p.target,s,p.tax);p.flat=scenario(p.quantity,p.limit,p.limit,s,p.tax);p.rewardRisk=m(p.upside.pnl/Math.max(.01,-p.downside.pnl));
 if(p.rewardRisk<.75)p.blocks.push('候選試驗成本後報酬／風險小於0.75；此門檻僅固定實驗假設');
 if(!p.goalFeasible)p.warnings.push(`想淨賺 ${s.goal} 需約 ${p.wanted}；超過近期壓力 ${p.pressure}，不增加股數追目標`);
 const ev=(stock.news||[]).filter(e=>!e.available_at||new Date(e.available_at)<=new Date(ctx.at)).filter(e=>e.included!==false).sort((a,b)=>Math.abs(b.impact_score||0)-Math.abs(a.impact_score||0)).slice(0,3);
 p.events=ev.map(e=>({id:e.id,title:e.title,url:e.source_url||e.url,summary:e.summary||e.mechanism||'',category:e.category_label||e.category,impact:e.impact_score,chain:e.chain||[],confirmation:e.confirmation||'',invalidation:e.invalidation||e.reversal_condition||'',kpi:e.watch_metric||'',missing:e.missing||[],evidence:(e.evidence||[]).slice(0,2),coverage:e.source_assessment?.coverage||'未標示',verified:!!e.source_assessment?.verified}));
 p.analysis=[{name:'新聞',known:p.events[0]?.summary||'沒有足以定方向的新事件',unknown:p.events[0]?.missing?.join('；')||'事件引起的報酬尚未量化'},{name:'價格',known:`收盤 ${p.limit}；月線 ${b.ma20??'缺'}；季線 ${b.ma60??'缺'}；壓力 ${p.pressure}`,unknown:'支撐與壓力是歷史價格區間，不是可達價格保證'},{name:'部位',known:`最高按 ${p.limit} × ${p.quantity} 股估計；風險情境 ${p.downside.pnl} 元`,unknown:'跳空可能超過停止損失；此為虛擬帳戶'},{name:'期限',known:`第 ${Math.min(5,s.hold)} 個交易日檢查；最多 ${s.hold} 個交易日`,unknown:'期限來自你的實驗設定，不是回測挑出的最優值'}];
 p.factors=copy(dec.factors||[]);p.originalReasons=copy(dec.reasons||[]);p.originalRisks=copy(dec.risks||[]);
 p.testLabel=s.strategy==='original'?'忠實原建議組':'候選股探索試驗';p.action=p.blocks.length?'不建立新試單':'可確認試買';return p;
}
export function newExperiment(s0,ctx,id=crypto.randomUUID()){
 const s=settings(s0);return {schema:1,version:LAB_VERSION,id,mode:ctx.mode,start:ctx.at,cursor:ctx.at,source:copy(ctx),settings:s,cash:m(s.capital),receivables:[],contributions:m(s.capital),units:s.capital,unitValue:1,peakUnit:1,maxDrawdown:0,position:null,orders:[],closed:[],events:[],revision:0,history:[{date:dayAt(ctx.at),at:ctx.at,equity:s.capital,pnl:0,cash:s.capital,unit:1}],createdAt:new Date().toISOString()};
}
function addEvent(r,type,payload,at=r.cursor){r.revision++;r.events.push({id:r.id+':'+r.revision,runId:r.id,seq:r.revision,type,at,recordedAt:new Date().toISOString(),payload:copy(payload)});return r}
export function approve(run,proposal,hash){const r=copy(run);if(proposal.blocks.length)throw Error('條件未通過：'+proposal.blocks.join('；'));if(r.position||r.orders.some(o=>o.status==='pending'))throw Error('已有持股或待成交試單，勿重複確認');if(proposal.decisionAt!==r.cursor)throw Error('試驗時間已變，請重算提案');if(proposal.settings.strategy!==r.settings.strategy)throw Error('規則不同，需另開試驗');if(proposal.validFor<dayAt(r.cursor))throw Error('試單已過期');if(proposal.downside.buy>r.cash)throw Error('現金不足');if(!hash)throw Error('提案未凍結雜湊');const o={id:crypto.randomUUID(),status:'pending',side:'buy',proposal:copy(proposal),hash,decisionAt:r.cursor};r.orders.push(o);return addEvent(r,'approve_buy',o)}
export function queueSell(run,cal){const r=copy(run);if(!r.position)throw Error('沒有試驗持股');if(r.orders.some(o=>o.status==='pending'))throw Error('已有待成交指令');const o={id:crypto.randomUUID(),status:'pending',side:'sell',symbol:r.position.symbol,quantity:r.position.quantity,validFor:decisionSession(r.cursor,cal),decisionAt:r.cursor};r.orders.push(o);return addEvent(r,'approve_sell',o)}
export function cancel(run,id){const r=copy(run),o=r.orders.find(x=>x.id===id&&x.status==='pending');if(!o)throw Error('沒有可取消指令');o.status='cancelled';return addEvent(r,'cancel_order',{id})}
export function deposit(run,amount){const r=copy(run);if(!Number.isFinite(amount)||amount<=0||amount>1e9)throw Error('虛擬入金金額不合法');r.cash=m(r.cash+amount);r.contributions=m(r.contributions+amount);r.units+=amount/r.unitValue;return addEvent(r,'virtual_deposit',{amount})}
export function updateSettings(run,p){const r=copy(run),s=settings({...r.settings,...p});if(s.strategy!==r.settings.strategy)throw Error('變更策略須另開試驗，不能改舊樣本');r.settings=s;return addEvent(r,'settings_for_future_only',s)}
export function balance(r){const val=r.position?m(r.position.quantity*r.position.mark):0,recv=m(r.receivables.reduce((a,b)=>a+b.amount,0)),eq=m(r.cash+recv+val),realized=m(r.closed.reduce((a,b)=>a+b.pnl,0)),unreal=r.position?m(val-r.position.cost):0;return {cash:r.cash,reserved:m(r.orders.filter(o=>o.status==='pending'&&o.side==='buy').reduce((a,o)=>a+o.proposal.downside.buy,0)),receivable:recv,marketValue:val,equity:eq,pnl:m(eq-r.contributions),realized,unrealized:unreal,returnPct:m((eq-r.contributions)/r.contributions*100),unitReturn:m((r.unitValue-1)*100),maxDrawdown:r.maxDrawdown,closed:r.closed.length,wins:r.closed.filter(t=>t.pnl>0).length,winRate:r.closed.length?m(r.closed.filter(t=>t.pnl>0).length/r.closed.length*100):null}}
/** Advance one completed daily bar. Throws before mutating on missing data.
 * Execution: next-session open with adverse slippage, capped by buy limit.
 * This is deliberately NOT 'a limit touched during the day therefore filled'.
 */
export function advance(run,date,bars,cal,wallNow=new Date()){
 if(!session(date,cal))throw Error('不是日曆中的交易日');if(new Date(date+'T13:30:00+08:00')>new Date(wallNow))throw Error('這個交易日尚未結束，不能提前產生答案');
 const next=nextReplayDate(run,cal);if(date!==next)throw Error('只能逐日往後推進，不可跳過或倒退');
 const r=copy(run);const end=date+'T16:00:00+08:00';
 const pending=r.orders.filter(o=>o.status==='pending');
 if(r.position)checkBar(bars[r.position.symbol],date);
 for(const o of pending){const d=o.side==='buy'?o.proposal.validFor:o.validFor;if(d===date)checkBar(bars[o.side==='buy'?o.proposal.symbol:o.symbol],date)}
 for(const x of r.receivables.filter(x=>x.date<=date)){r.cash=m(r.cash+x.amount);addEvent(r,'settlement',x,end)}r.receivables=r.receivables.filter(x=>x.date>date);
 function sell(raw,why,order=null){const h=r.position,s=h.plan.settings,price=m(raw*(1-s.slip)),gross=m(price*h.quantity),f=fee(h.quantity,price,s),tax=m(gross*h.plan.tax),proceeds=m(gross-f-tax),pnl=m(proceeds-h.cost),settlement=nextSession(date,cal,2);const t={id:crypto.randomUUID(),symbol:h.symbol,name:h.name,quantity:h.quantity,entryDate:h.entryDate,exitDate:date,entry:h.entry,exit:price,cost:h.cost,proceeds,fee:f,tax,pnl,returnPct:m(pnl/h.cost*100),why,held:h.sessions,settlement,planHash:h.planHash,plan:h.plan};r.closed.push(t);r.receivables.push({date:settlement,amount:proceeds});r.position=null;if(order)order.status='filled';addEvent(r,'simulated_sell',t,end)}
 let hadPosition=!!r.position;
 for(const o of pending){const valid=o.side==='buy'?o.proposal.validFor:o.validFor;
  if(valid<date){o.status='expired';addEvent(r,'unfilled',{id:o.id,reason:'超過原有效日'},end);continue}if(valid!==date)continue;
  const p=o.proposal,b=bars[o.side==='buy'?p.symbol:o.symbol];
  if(b.open===b.high&&b.high===b.low&&b.low===b.close){if(o.side==='sell')throw Error('單一價位日無法確認賣出流動性；保留持股等待核對');o.status='uncertain';addEvent(r,'unfilled',{id:o.id,reason:'單一價位日，日K無法證明可成交'},end);continue}
  if(o.side==='sell'){if(!r.position)throw Error('沒有可賣持股');sell(b.open,'你確認的試賣，下一有效日開盤代理',o);continue}
  if(r.position){o.status='rejected';addEvent(r,'unfilled',{id:o.id,reason:'已有持股'},end);continue}
  const fill=m(b.open*(1+p.settings.slip)),cost=m(fill*p.quantity+fee(p.quantity,fill,p.settings));
  if(fill>p.limit||b.open<=p.stop||b.open>=p.target||p.quantity>Math.floor(b.volume*.01)||cost>r.cash){o.status='unfilled';addEvent(r,'unfilled',{id:o.id,reason:fill>p.limit?'開盤含滑價超過限價；不假設日內觸價即成交':b.open<=p.stop?'開盤已跌破原停止條件':b.open>=p.target?'開盤已超出原目標情境':cost>r.cash?'虛擬現金不足':'超過每日成交量1%研究上限'},end);continue}
  r.cash=m(r.cash-cost);o.status='filled';r.position={symbol:p.symbol,name:p.name,quantity:p.quantity,entry:fill,cost,entryDate:date,sessions:0,mark:fill,plan:copy(p),planHash:o.hash};addEvent(r,'simulated_buy',{order:o.id,symbol:p.symbol,quantity:p.quantity,price:fill,cost,planHash:o.hash},end);
 }
 if(r.position){const h=r.position,b=bars[h.symbol];checkBar(b,date);h.sessions++;h.mark=b.close;
  const p=h.plan,stop=p.stop,target=p.target;if(p.settings.autoExit){if(b.open<=stop&&h.entryDate!==date)sell(b.open,'跳空停損：以較差開盤代理');else if(b.open>=target&&h.entryDate!==date)sell(b.open,'跳空到目標：開盤代理');else if(b.low<=stop)sell(stop,b.high>=target?'日內同觸停止及目標，採停止優先':'觸及預先確認停止條件');else if(b.high>=target)sell(target,'觸及預先確認目標情境');else if(h.sessions>=p.settings.hold)sell(b.close,'已到預先確認的最長持有日');}
 }
 r.cursor=end;const bal=balance(r);r.unitValue=bal.equity/r.units;r.peakUnit=Math.max(r.peakUnit,r.unitValue);r.maxDrawdown=m(Math.min(r.maxDrawdown,(r.unitValue/r.peakUnit-1)*100));r.history.push({date,at:end,equity:bal.equity,pnl:bal.pnl,cash:r.cash,unit:r.unitValue});return addEvent(r,'advance_day',{date,barHashes:null,equity:bal.equity,note:'日K代理，不代表盤中零股真實成交'},end);
}
export function nextReplayDate(run,cal){const d=dayAt(run.cursor);const h=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(run.cursor)).replace(':',''));return session(d,cal)&&h<1330?d:nextSession(d,cal)}
export function validateRun(r){if(!r||r.schema!==1||!r.id||!dateValid(dayAt(r.cursor)))throw Error('試驗格式不正確');settings(r.settings);if(!Array.isArray(r.events)||r.events.length!==r.revision)throw Error('試驗事件數量不符');const ids=new Set;let at=r.start;for(const e of r.events){if(e.runId!==r.id||ids.has(e.id)||e.seq!==ids.size+1||new Date(e.at)<new Date(at))throw Error('事件重複、順序不符或倒退');ids.add(e.id);at=e.at}const b=balance(r);if(r.cash<-.01||Math.abs(b.pnl-b.realized-b.unrealized)>.06)throw Error('現金或帳務恆等式不符');if(r.position&&(!Number.isInteger(r.position.quantity)||r.position.quantity<=0))throw Error('試驗持股無效');return true}
/** Load the next evening/early-morning snapshot without skipping a market day. */
export function attachSnapshot(run,ctx,cal){const r=copy(run);if(new Date(ctx.at)<new Date(r.cursor))throw Error('不倒退試驗時間');const next=nextReplayDate(r,cal);if(new Date(ctx.at)>=new Date(next+'T09:00:00+08:00'))throw Error('先結算下一交易日，不能提前載入盤後訊號');if(new Date(ctx.generatedAt)>new Date(ctx.at))throw Error('來源尚未可用');r.source=copy(ctx);r.cursor=ctx.at;return addEvent(r,'snapshot_update',{path:ctx.path,hash:ctx.hash,generatedAt:ctx.generatedAt},ctx.at)}
