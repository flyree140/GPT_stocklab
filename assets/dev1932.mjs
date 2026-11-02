import {previewPrices} from './reprice1933.mjs';
import * as U from './updates1933.mjs';
import * as D from './dev1932-engine.mjs';import * as P from './paper-engine.mjs';import {DeveloperCloud} from './dev1932-cloud.mjs';
const $=s=>document.querySelector(s),E=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const f=(x,n=2)=>Number.isFinite(x)?x.toLocaleString('zh-TW',{maximumFractionDigits:n}):'未取得';
const KEY='stocklab-dev1932-batches-v1';let batches=[],snap,ctx,cal,rows=[],research={},outcomes=null,manifest,cloud=null,busy=false;
let workingSnapshot=null;
let priceStatus=null,refreshAt=null,loadError=false,cloudConfigSource='',lastAuto=0;
const REVEAL_KEY='dev1933-reveal-permission';let revealAllowed=new Set;try{revealAllowed=new Set(JSON.parse(localStorage.getItem(REVEAL_KEY)||'[]'))}catch{}
try{batches=JSON.parse(localStorage.getItem(KEY)||'[]')}catch{message('本機批次格式異常；未覆蓋舊資料，請先備份')}
function message(s){$('#message').hidden=false;$('#message').textContent=s;}
function save(){try{localStorage.setItem(KEY,JSON.stringify(batches));localStorage.setItem('dev1933-cloud-dirty','1');updateCloudUI()}catch(e){throw Error('瀏覽器儲存空間不足；請立即下載完整批次備份。'+e.message)}}
async function fetchJ(path){
 const u=new URL(path,location.href);if(u.origin!==location.origin)throw Error('拒絕跨站資料路徑');u.searchParams.set('_sl',String(Date.now()));
 const response=await fetch(u,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!response.ok)throw Error(`${path} 回傳${response.status}`);return response.json();
}
function quoteDates(){return [...new Set(((workingSnapshot||snap)?.stocks||[]).map(r=>r.candles?.at(-1)?.date).filter(Boolean))].sort()}
function clockPanel(){
 const c=U.taipeiClock();$('#taipeiClock').textContent=c.text+' 台北時間';
 let sessionText='日曆待核對';try{sessionText=P.session(c.date,cal)?c.hhmm<900?'開盤前':c.hhmm<1330?'盤中：不能拿未完成日K結算':'已收盤：仍須等行情來源與部署':'休市日：保留試單，不製造成交'}catch{}
 $('#sessionLabel').textContent=sessionText;
 $('#dataHealth').innerHTML=metric('分析快照',snap?.as_of||'未讀取',snap?.generated_at||'')+metric('計畫價格日期',quoteDates().at(-1)||'未取得','價格可更新；原分析時間另列，非即時價')+
  metric('行情補價工作',priceStatus?.at?U.taipeiClock(priceStatus.at).text:'尚無補價紀錄',priceStatus?`需要 ${priceStatus.required_close_date||'日曆待核對'}；待補 ${priceStatus.queued||0}；來源失敗 ${priceStatus.failed?.length||0}`:'部署後請執行 Refresh market data (no Qwen)')+
  metric('瀏覽器重讀',refreshAt?U.taipeiClock(refreshAt).text:'尚未重讀','重讀已發布JSON，不會在Pages啟動爬蟲');
 $('#localClockNote').textContent='時區固定 Asia/Taipei；時間取自裝置時鐘。裝置時間有誤時，請開啟系統自動校時。排程為目標時間，不保證準時。';
}
async function refreshCalendarAndStatus(){
 try{const incoming=await fetchJ('assets/paper-calendar.json');cal=cal?P.compatibleCalendar(cal,incoming):incoming}catch(e){if(!cal)throw e;message('日曆更新失敗，保留原版：'+e.message)}
 try{priceStatus=await fetchJ('data/developer1932/price_refresh.json')}catch{priceStatus=null}
 refreshAt=new Date().toISOString();clockPanel();
}
function settings(){return {...D.DEFAULT,capital:Number($('#capital').value),budget:Number($('#capital').value),maxLoss:Number($('#maxLoss').value),hold:Number($('#hold').value),goal:Number($('#goal').value),strategy:$('#strategy').value}}
function metric(a,b,c=''){return `<div class="metric"><small>${E(a)}</small><strong>${E(b)}</strong><small>${E(c)}</small></div>`}
function download(name,obj){const u=URL.createObjectURL(new Blob([typeof obj==='string'?obj:JSON.stringify(obj,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),2000)}
function proxy(symbol){return research?.stocks?.find(s=>s.symbol===symbol)?.foreign_defense||{status:'missing',alert:'未累積可核對法人資料'};}
async function load(){
 const demo=$('#dataMode').value==='demo',prefix=demo?'data/demo/developer/':'data/';loadError=false;
 try{
  await refreshCalendarAndStatus();manifest=await fetchJ(prefix+'manifest.json');
  const selection=$('#snapshotSelect').value;
  if(!$('#snapshotSelect').options.length||$('#snapshotSelect').dataset.mode!==prefix){
   $('#snapshotSelect').innerHTML='<option value="'+prefix+'latest.json">最新快照 → 從現在起計畫</option>'+(manifest.snapshots||[]).map(r=>`<option value="${E(r.path)}">${E(r.date)} / ${E(r.generated_at||'')}（歷史重播）</option>`).join('');$('#snapshotSelect').dataset.mode=prefix;
  }
  const path=$('#snapshotSelect').value,sourceURL=new URL(path,location.href);if(sourceURL.origin!==location.origin)throw Error('快照路徑須在本站');sourceURL.searchParams.set('_sl',String(Date.now()));
  const response=await fetch(sourceURL,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!response.ok)throw Error('缺快照 '+path);
  const raw=await response.text();snap=JSON.parse(raw);if(!Array.isArray(snap.stocks))throw Error('快照缺stocks');
  const hash=await P.sha(raw),generated=snap.generated_at;
  const mode=demo||snap.demo?'demo':path===prefix+'latest.json'?'forward':'historical';
  // A new latest-plan decision is made NOW, never silently backdated to a closed open.
  const at=mode==='forward'?new Date().toISOString():generated;
  ctx={path,hash,generatedAt:generated,at,asOf:mode==='forward'?P.dayAt(at):snap.as_of,mode,cal};
  workingSnapshot=P.copy(snap);
  if(mode==='forward'){
   const prices={};
   for(let i=0;i<snap.stocks.length;i+=5){await Promise.all(snap.stocks.slice(i,i+5).map(async stock=>{try{prices[stock.symbol]=await fetchJ(`data/market/${stock.symbol.replaceAll('.','_')}.json`)}catch{/* Original evidence remains; stale-date validator will explain. */}}));}
   const projected=await previewPrices(snap,ctx,prices);workingSnapshot=projected.snapshot;ctx.priceEvidence=projected.evidence;
  }

  try{research=await fetchJ(demo?'data/demo/developer/research.json':'data/research192/latest.json');if(research.cutoff!==generated||(!demo&&research.source_file_sha256!==hash))research={};}catch{research={};}
  $('#source').textContent=(mode==='demo'?'合成練習，不是真實績效。':mode==='forward'?'向前計畫：從你目前確認時間起，不倒填今天已經過去的開盤價。':'明確選擇的歷史重播，與前瞻績效分開。')+' 來源 '+path+'；產生 '+generated+'；'+snap.stocks.length+'檔分析。';
  recalc();renderBatches();clockPanel();return true;
 }catch(e){loadError=true;message('讀取失敗：'+e.message+'。原已確認批次與本機資料保留，不是市場看空。');workingSnapshot=null;rows=[];renderRows();clockPanel();return false;}
}
function recalc(){try{if(!snap||!ctx)return;rows=D.prepare(workingSnapshot||snap,ctx,settings());renderRows();}catch(e){message(e.message)}}
function renderRows(){const good=rows.filter(r=>r.eligible);$('#counts').innerHTML=metric('全部留存觀察',rows.length,'含觀望／避開／未建單')+metric('可確認試單',good.length,'每檔獨立資金，不共享')+metric('保留未建單',rows.length-good.length,'也列入固定期限研究')+metric('Qwen新呼叫','0','配置與結算只用CPU');$('#approveNote').textContent=`${good.length}筆建立試單；${rows.length-good.length}筆保留拒絕理由，不強迫買入。`;$('#approveAll').disabled=!rows.length||busy;
 const query=$('#search').value.trim().toLowerCase(),filter=$('#filter').value;
 $('#planRows').innerHTML=rows.filter(r=>(!query||(r.symbol+r.name+r.proposal.blocks.join(' ')).toLowerCase().includes(query))&&(filter==='all'||filter==='eligible'&&r.eligible||filter==='blocked'&&!r.eligible||filter==='foreign'&&proxy(r.symbol).status==='available')).map(r=>{const p=r.proposal,fx=proxy(r.symbol);return `<tr><td><strong>${E(r.name)}</strong><small>${E(r.symbol)}</small><small>${E(r.originalLabel)} / ${f(p.original?.score,1)}分</small></td><td><span class="badge ${r.eligible?'':'warn'}">${r.eligible?'可確認試買':'未建試單・仍觀察'}</span><small>${E(p.blocks.join('；')||p.originalReasons?.[0]||'價格與固定研究條件通過')}</small></td><td><b>${r.eligible?p.quantity:0}股</b><small>最高 ${f(p.limit)} 元</small><small>${r.eligible?'支出 '+f(p.downside?.buy):'未建單支出 0'}</small></td><td>停 ${f(p.stop)}<br>目標 ${f(p.target)}<small>損失 ${f(p.downside?.pnl)}／情境收益 ${f(p.upside?.pnl)}</small></td><td>${p.settings.hold}交易日<small>${E(p.deadline||'跨年日期待公告')}</small></td><td>${f(fx.value)}<small>${E(fx.alert)}</small><small>非外資真實成本</small></td><td><button class="secondary" data-detail="${E(r.symbol)}">六面向與依據</button></td></tr>`}).join('')||'<tr><td colspan="7">沒有符合條件的列；這不會刪除原分析。</td></tr>';
}
function detail(symbol){const row=rows.find(r=>r.symbol===symbol);if(!row)return;const p=row.proposal,st=snap.stocks.find(s=>s.symbol===symbol),extra=research.stocks?.find(s=>s.symbol===symbol),fx=proxy(symbol);
 $('#detailBody').innerHTML=`<div class="eyebrow">完整研究 / ${E(symbol)}</div><h1>${E(row.name)}</h1><p class="note">${E(p.blocks.join('；')||'可確認虛擬試買。來源與規則固定，並非真實投資建議。')}</p><div class="grid">${(p.factors||[]).map(v=>`<div class="factor"><strong>${E(v.name||v.key)}</strong><div class="factorbar"><i style="width:${Number.isFinite(v.score)?Math.max(0,Math.min(100,v.score)):0}%"></i></div>${f(v.score,1)}<p class="muted">${E(v.note||'原始規則分，不是上漲機率')}</p></div>`).join('')}</div><h2>支持與反對</h2><p>${E((p.originalReasons||[]).join('；')||'沒有提供')}</p><p class="muted">${E([...(p.originalRisks||[]),...(p.warnings||[])].join('；'))}</p><h2>外資流向支撐代理</h2><p>${E(fx.alert)} · ${f(fx.value)} · ${fx.matched_sessions||0}期</p><p class="muted">僅以典型價乘正淨買股數估計，並非持倉成本／保證支撐；缺值不造線。</p><h2>新聞傳導與可驗證條件</h2>${(p.events||[]).map(e=>`<div class="factor"><strong>${E(e.title)}</strong><p>${E(e.summary)}</p><p>確認：${E(e.confirmation||'缺證據')}<br>失效：${E(e.invalidation||'缺證據')}<br>KPI：${E(e.kpi||'未提供')}</p></div>`).join('')||'<p>這份原始快照沒有可用新聞；不宣稱Qwen讀過全文。</p>'}<h2>自有權重結果</h2><p>${extra?.analyses?.length?E(extra.analyses.map(a=>a.output.mechanisms?.map(m=>m.claim).join('；')).join('；')):'這份快照沒有同時點的有效adapter輸出；不把其他日期的分析拼過來。'}</p><details><summary>全部資料缺口與計畫JSON</summary><pre>${E(JSON.stringify({plan:p,six_factors:extra?.factors,foreign_defense:fx},null,2))}</pre></details>`;$('#detail').showModal();$('#detail').setAttribute('tabindex','-1');$('#detail').focus({preventScroll:true});$('#detail').scrollTop=0;}
function renderBatches(){
 $('#batchList').innerHTML=batches.length?batches.slice().reverse().map(b=>{
  const x=D.batchSummary(b);return `<details class="card" ${batches.at(-1)?.id===b.id?'open':''}><summary>${E(b.context.asOf)} · ${x.observed}檔觀察 / ${x.eligible}筆試單 · ${b.deletedAt?'已回收':b.context.mode==='historical'?'歷史重播':b.context.mode==='demo'?'合成練習':'向前登記'} · 版本${b.revision}</summary>
   <p><b>已確認只是建立試單，不代表買進。</b> 待處理 ${x.pending}、已虛擬持有 ${x.holding}、已完成 ${x.completed}、只保存分析 ${x.blocked}。</p>
   ${x.eligible===0?'<p class="note">這批0檔通過規則，只有觀察紀錄，因此不會產生成交。請查看每列未通過條件；日結不會替你硬買。</p>':''}
   <p class="muted">獨立帳戶平均報酬 ${f(x.meanIndependentReturnPct)}%，不是一個共用資金投組。批次確認：${E(b.createdAt)}</p>
   <div class="table-scroll"><table><thead><tr><th>股票</th><th>現在在哪一步</th><th>原建議</th><th>有效買進日／需補日期</th><th>成交或未成交證據</th><th>損益</th></tr></thead><tbody>${b.rows.map(r=>{
    const a=r.account,bal=a?P.balance(a):null,t=a?.closed?.at(-1),h=a?.position,o=a?.orders?.at(-1),state=U.rowState(r,b,cal||b.context.cal),check=r.lastCheck;
    const text=r.lastError||check?.message||state.message;
    const unfilled=[...(a?.events||[])].reverse().find(e=>e.type==='unfilled')?.payload?.reason;
    const status=r.lastError&&state.state!=='await_close'?(check?.state||'missing_price'):state.state;
    return `<tr><td>${E(r.name)}<small>${E(r.symbol)}</small></td><td><span class="badge ${['holding','closed'].includes(status)?'':'warn'}">${E(U.STATE_LABELS[status]||D.status(r))}</span><small>${E(text)}</small></td><td>${E(r.originalLabel)}</td><td>${E(o?.proposal?.validFor||'未建單')}<small>下一核對：${E(check?.date||state.date||'—')}</small><small>最新行情：${E(check?.latest||'尚未讀取')}</small></td><td>${h?E(h.entryDate)+' @ '+f(h.entry):t?E(t.entryDate)+' → '+E(t.exitDate):E(unfilled||'尚未成交')}<small>${h?h.quantity+'股':t?t.quantity+'股':o?.proposal?.quantity?o.proposal.quantity+'股待判定':''}</small><small>${E(check?.file||state.file||'')}</small></td><td>${f(bal?.pnl)}<small>已實現 ${f(bal?.realized)}／未實現 ${f(bal?.unrealized)}</small></td></tr>`;
   }).join('')}</tbody></table></div><button class="secondary" data-trash="${E(b.id)}">${b.deletedAt?'還原':'移到回收桶（保留紀錄）'}</button></details>`;
 }).join(''):'<p>尚未確認批次。回到「全部配置」檢查後建立；無合格者只會保存觀察，不會成交。</p>';
}
async function guarded(fn){
 if(busy)return;busy=true;$('#settle').disabled=true;$('#refreshPublished').disabled=true;$('#approveAll').disabled=true;
 try{await fn()}catch(e){message(e.message)}finally{busy=false;$('#settle').disabled=false;$('#refreshPublished').disabled=false;renderRows();updateCloudUI()}
}
$('#approveAll').onclick=()=>guarded(async()=>{
 const previous=ctx?P.copy(ctx):null;$('#workStatus').textContent='先重讀最新已發布的快照、日曆與更新狀態…';
 if(!await load())throw Error('重讀失敗，沒有新增批次；原批次保留。');
 if(previous&&U.approvalChanged(previous,ctx,cal)){message('資料、模式或有效交易日已更新，提案已重算。請重新看過價格與股數，再確認；本次沒有送出試單。');return;}
 const n=rows.filter(r=>r.eligible).length;
 if(!confirm(n?`確認${n}筆虛擬試單？有效日由計畫決定，收盤取得完整日K才回算。未通過者只保存觀察。`:'目前0筆合格試單。是否只保存這批觀察？這不會買進，日結也不會強迫成交。'))return;
 const b=await D.confirmBatch(rows,ctx,settings(),batches);await D.validateBatch(b);batches.push(b);save();renderBatches();tab('batches');
 message(n?`已確認${n}筆試單，尚未成交。請看每列有效日；下一步「更新並結算」。`:'已保存觀察批次（0筆試單）；請看未通過原因，不需要反覆日結。');
 $('#workStatus').textContent='已在本機保存；尚未同步Google時，雲端顯示「待同步」。';
});
async function settleBatches(automatic=false){
 const active=batches.filter(b=>!b.deletedAt);
 if(!active.length){message('尚無啟用中的批次；請先確認配置。');return;}
 if(!automatic){
  if(!confirm('更新已發布行情，核對全部已確認試單；歷史批次會讀取後續行情。這不會聯絡券商，也不保證限價能成交。是否繼續？'))return;
  for(const b of active)revealAllowed.add(b.id);localStorage.setItem(REVEAL_KEY,JSON.stringify([...revealAllowed]));
 }
 await refreshCalendarAndStatus();
 const cache={},total={batches:0,bought:0,sold:0,unfilled:0,sessions:0,errors:0,observations:0},at=new Date();
 for(let i=0;i<batches.length;i++){
  const b=batches[i];if(b.deletedAt||automatic&&b.context.mode!=='forward'&&!revealAllowed.has(b.id))continue;
  // Settles the immutable plan, never replaces it with today's recommendation.
  const market={},prefix=b.context.mode==='demo'?'data/demo/developer/market/':'data/market/';
  for(const row of b.rows.filter(r=>r.account)){
   const key=prefix+row.symbol.replaceAll('.','_')+'.json';$('#workStatus').textContent='重讀行情：'+key;
   if(!(key in cache)){try{cache[key]=await fetchJ(key)}catch(e){cache[key]={candles:[],_transportError:`行情檔讀取失敗：${key}；${e.message}。已確認試單保留，不是沒有交易紀錄。`};}}
   market[row.symbol]=cache[key];
  }
  try{const bc=P.compatibleCalendar(b.context.cal,cal);const next=await D.advanceBatch(b,market,bc,at);await D.validateBatch(next);
   const diff=U.changeSummary(b,next);Object.keys(diff).forEach(k=>total[k]+=diff[k]);batches[i]=next;total.batches++;save();
  }catch(e){total.errors++;message('批次 '+b.id+' 暫停：'+e.message+'；其他批次繼續。');}
 }
 renderBatches();$('#workStatus').textContent=U.summaryMessage(total);message(U.summaryMessage(total));
 $('#settlementSummary').innerHTML=metric('本次虛擬買進',total.bought+'筆','不是券商交易')+metric('本次虛擬賣出',total.sold+'筆','日K固定規則')+metric('限價等未成交',total.unfilled+'筆','原因保留')+metric('仍需處理',total.errors+'檔','下方指出缺資料或未收盤');
 refreshAt=new Date().toISOString();clockPanel();return total;
}
$('#settle').onclick=()=>guarded(()=>settleBatches(false));
$('#refreshPublished').onclick=()=>guarded(async()=>{await load();message('已重讀網站發布資料。這不是啟動爬蟲；行情仍舊時，點「補抓行情工作流程」並Run workflow。');});
setInterval(()=>{
 clockPanel();if(!$('#autoSettle')?.checked||document.visibilityState!=='visible'||busy||Date.now()-lastAuto<300000)return;
 const active=batches.some(b=>!b.deletedAt&&(b.context.mode==='forward'||revealAllowed.has(b.id))&&b.rows.some(r=>r.account&&(r.account.position||r.account.orders.some(o=>o.status==='pending')||r.account.receivables.length)));
 if(active){lastAuto=Date.now();guarded(()=>settleBatches(true));}
},15000);
$('#autoSettle').onchange=()=>{localStorage.setItem('dev1933-auto-settle',$('#autoSettle').checked?'1':'0');message($('#autoSettle').checked?'已啟用本頁開啟且可見時每5分鐘核對；歷史資料需先手動同意揭曉。':'已關閉自動核對。');};
$('#autoSettle').checked=localStorage.getItem('dev1933-auto-settle')==='1';
function tab(t){for(const id of ['plans','batches','outcomes','cloudPane'])$('#'+id).hidden=id!==t;document.querySelectorAll('[data-tab]').forEach(b=>b.className=b.dataset.tab===t?'':'secondary')}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));$('#recalc').onclick=recalc;$('#search').oninput=renderRows;$('#filter').onchange=renderRows;$('#dataMode').onchange=load;$('#snapshotSelect').onchange=load;
$('#planRows').onclick=e=>{const b=e.target.closest('[data-detail]');if(b)detail(b.dataset.detail)};$('#closeDetail').onclick=()=>$('#detail').close();
$('#batchList').onclick=e=>{const btn=e.target.closest('[data-trash]');if(btn){const i=batches.findIndex(b=>b.id===btn.dataset.trash);batches[i]=D.trash(batches[i],!batches[i].deletedAt);save();renderBatches()}};
$('#backup').onclick=()=>download('StockLab-developer-private-backup.json',{schema:'developer1932-backup-1',batches});
$('#import').onchange=e=>guarded(async()=>{const obj=JSON.parse(await e.target.files[0].text());if(obj.schema!=='developer1932-backup-1'||!Array.isArray(obj.batches))throw Error('不是開發者備份');for(const b of obj.batches){await D.validateBatch(b);const old=batches.find(x=>x.id===b.id);if(old&&P.canonical(old)!==P.canonical(b))throw Error('同ID內容不同，請先另存現況備份，不自動覆寫')};for(const b of obj.batches)if(!batches.some(x=>x.id===b.id))batches.push(b);save();renderBatches();message('備份驗證後還原完成')});
$('#reveal').onclick=()=>guarded(async()=>{if(!confirm('揭曉全部股票後續表現？這不是實際成交帳，也不是原標籤獲利率。'))return;outcomes=await fetchJ('data/developer1932/outcomes.json');renderOutcomes();$('#outCSV').disabled=false});
const outcomeLabel=s=>({mature:'已成熟可核對',pending:'持有期未走完',missing_price:'缺對應日K',corporate_action:'公司行動待核對',calendar_pending:'日曆待更新',uncertain_flat_bar:'平價日無法確認成交',budget_insufficient:'預算不足',liquidity_cap:'流動性限制'}[s]||s);
function renderOutcomes(){if(!outcomes)return;const h=$('#horizon').value;const ms=outcomes.summary||{};$('#outSummary').innerHTML='<div class="metrics">'+Object.entries(ms).map(([k,v])=>metric(k==='prospective_registered'?'前瞻登記成熟數':'回溯參考成熟數',v[h]?.n||0,'獨立進場日期 '+(v[h]?.unique_entry_dates||0))).join('')+metric('等額獨立預算',f(outcomes.budget_per_symbol),'不共用你的本金')+metric('未成熟／缺資料',outcomes.rows.filter(r=>r.outcomes[h]?.status!=='mature').length,'保留，不算贏或輸')+'</div>';
 $('#outTable').innerHTML=`<table><thead><tr><th>股票／訊號</th><th>原標籤／分數</th><th>資料性質</th><th>狀態</th><th>股數／成本</th><th>淨報酬</th><th>相對0050</th></tr></thead><tbody>${outcomes.rows.slice().reverse().map(r=>{const o=r.outcomes[h]||{};return `<tr><td>${E(r.name)}<small>${E(r.generated_at)}</small></td><td>${E(r.original_label)}<small>${f(r.score,1)}</small></td><td>${r.sample_mode==='prospective_registered'?'前瞻登記':'回溯參考'}</td><td>${E(outcomeLabel(o.status))}<small>${E(o.needed_until||o.date||o.exit_date||'')}</small></td><td>${o.shares??'—'}<small>${f(o.buy_cost)}</small></td><td>${f(o.return_on_cost_pct)}%<small>損益 ${f(o.pnl)} 元</small></td><td>${f(o.excess_budget_pct)}pp</td></tr>`}).join('')}</tbody></table>`;}
$('#horizon').onchange=renderOutcomes;$('#outCSV').onclick=()=>{if(!outcomes)return;const q=v=>'"'+String(v??'').replaceAll('"','""')+'"';const a=[['symbol','generated_at','original_label','mode','horizon','status','shares','pnl','net_return_cost','excess_budget']];for(const r of outcomes.rows)for(const [h,o] of Object.entries(r.outcomes))a.push([r.symbol,r.generated_at,r.original_label,r.sample_mode,h,o.status,o.shares,o.pnl,o.return_on_cost_pct,o.excess_budget_pct]);download('all-analyzed-outcomes.csv','\ufeff'+a.map(r=>r.map(q).join(',')).join('\n'))};
function validClient(id){return /^[0-9]+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com$/.test(id||'')}
function updateCloudUI(){
 if(!$('#cloudSetupState'))return;
 const authed=!!cloud?.token&&Date.now()<cloud.expires-30000;
 $('#cloudSetupState').textContent=validClient(cloud?.clientId)?'① Client ID 已設定（'+cloudConfigSource+'）':'① 尚未設定Client ID：貼在下方，或參考一次性教學';
 $('#cloudAuthState').textContent=authed?'② 已授權Google，Token只存在本頁記憶體':'② 尚未登入／授權到期：本機批次仍保留';
 $('#cloudBookState').textContent=cloud?.sheet?'③ 已選開發者活頁簿':'③ 未選活頁簿：先尋找既有，沒有才建立';
 $('#cloudSyncState').textContent=localStorage.getItem('dev1933-cloud-dirty')==='1'?'④ 本機有未同步更動':'④ 最近核對：'+(localStorage.getItem('dev1933-cloud-at')?U.taipeiClock(localStorage.getItem('dev1933-cloud-at')).text+' 台北':'尚無');
 for(const id of ['createCloud','listCloud'])$('#'+id).disabled=!authed||busy;
 for(const id of ['saveCloud','restoreCloud'])$('#'+id).disabled=!authed||!cloud?.sheet||busy;
 $('#openWorkbook').hidden=!cloud?.sheet;if(cloud?.sheet)$('#openWorkbook').href='https://docs.google.com/spreadsheets/d/'+encodeURIComponent(cloud.sheet)+'/edit';
}
async function initCloud(){
 let id=localStorage.getItem('dev1933-client-id')||'',cfg={};cloudConfigSource='本頁公開ID';
 if(!validClient(id)){try{cfg=await fetchJ('cloud-config.json')}catch{}id=cfg.client_id||'';cloudConfigSource='cloud-config.json';}
 if(!validClient(id)){
  const base=location.pathname.replace(/[^/]*$/,'');
  for(const key of ['stocklab-paperlab-1:'+base+'cloud','stocklab18:'+base+'cloud19']){try{const x=JSON.parse(localStorage.getItem(key)||'{}');if(validClient(x.clientId)){id=x.clientId;cloudConfigSource='沿用同瀏覽器先前設定';break}}catch{}}
 }
 cloud=new DeveloperCloud({clientId:id,onStatus:()=>updateCloudUI()});$('#developerClientId').value=id;
 if(validClient(id))cloud.loadIdentity().catch(e=>{$('#cloudStatus').textContent=e.message});updateCloudUI();
}
$('#saveClientId').onclick=()=>guarded(async()=>{const id=$('#developerClientId').value.trim();if(!validClient(id))throw Error('請貼公開OAuth Web Client ID（...apps.googleusercontent.com），不是Client Secret');
 if(cloud.clientId!==id)cloud.disconnect();cloud.clientId=id;cloudConfigSource='本頁公開ID';localStorage.setItem('dev1933-client-id',id);await cloud.loadIdentity();$('#cloudStatus').textContent='設定已保存；按「登入Google」。不會上傳ID以外的密鑰。';});
$('#login').onclick=()=>guarded(async()=>{await cloud.connect();const prev=localStorage.getItem('dev1932-sheet');
 if(prev){try{await cloud.select(prev);$('#cloudStatus').textContent='已登入並選回上次開發者活頁簿。'}catch{cloud.sheet=null;$('#cloudStatus').textContent='已登入，但上次活頁簿無法選取；請尋找既有或建立新的。';}}
 else $('#cloudStatus').textContent='已登入Google。先尋找既有開發者活頁簿，沒有再建立。';});
$('#createCloud').onclick=()=>guarded(async()=>{if(cloud.sheet&&!confirm('已選擇一份活頁簿。仍要另建？通常直接按保存即可。'))return;
 const id=await cloud.create();localStorage.setItem('dev1932-sheet',id);$('#cloudStatus').textContent='私人開發者活頁簿已建立；尚未存入批次。請按「保存全部並讀回核對」。';});
$('#listCloud').onclick=()=>guarded(async()=>{const files=await cloud.discover();$('#cloudSelect').innerHTML='<option value="">選擇</option>'+files.map(x=>`<option value="${E(x.id)}">${E(x.name)}</option>`).join('');$('#cloudStatus').textContent=files.length?`找到${files.length}份，請選擇。`:'沒有本應用建立的開發者活頁簿；請建立新的。個人帳本與此處分開。';});
$('#cloudSelect').onchange=()=>guarded(async()=>{if(!$('#cloudSelect').value)return;await cloud.select($('#cloudSelect').value);localStorage.setItem('dev1932-sheet',cloud.sheet);$('#cloudStatus').textContent='已選擇；接著保存或從雲端還原。';});
$('#saveCloud').onclick=()=>guarded(async()=>{if(!batches.length)throw Error('本機沒有已確認批次；建立活頁簿不會自動產生交易。');await cloud.saveBatches(batches);
 localStorage.setItem('dev1933-cloud-dirty','0');localStorage.setItem('dev1933-cloud-at',new Date().toISOString());$('#cloudStatus').textContent='全部批次已寫入並讀回雜湊核對；可打開Google活頁簿。';});
$('#restoreCloud').onclick=()=>guarded(async()=>{const remote=await cloud.readBatches(),candidate=P.copy(batches);
 for(const b of remote){const i=candidate.findIndex(x=>x.id===b.id),old=candidate[i];if(!old){candidate.push(b);continue}
 if(P.canonical(old)===P.canonical(b))continue;
 if(b.revision>old.revision&&P.canonical(old.events)===P.canonical(b.events.slice(0,old.events.length))){candidate[i]=b;continue}
 if(old.revision>b.revision&&P.canonical(b.events)===P.canonical(old.events.slice(0,b.events.length)))continue;
 throw Error('本機與雲端事件歷史分岔；請先下載本機備份，不自動覆蓋。');}
 batches=candidate;save();renderBatches();$('#cloudStatus').textContent='已還原可核對的較新版本；不倒退本機新版本，不合併分岔。';});
$('#cloudLogout').onclick=()=>{cloud.disconnect();$('#cloudStatus').textContent='已登出。資料與公開Client ID保留；沒有刪除雲端檔案。';updateCloudUI();};
await initCloud();for(const b of batches)await D.validateBatch(b).catch(e=>message('本機備份需核對：'+e.message));await load();
if(location.hash==='#cloud')tab('cloudPane');
