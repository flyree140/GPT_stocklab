// Read-only research rendering + conservative hypothetical sizing.
export const esc=x=>String(x??'未取得').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const num=(x,d=2)=>Number.isFinite(x)?x.toLocaleString('zh-TW',{maximumFractionDigits:d}):'未取得';
export function safeLink(url){try{const u=new URL(url);return ['http:','https:'].includes(u.protocol)?u.href:''}catch{return ''}}
export function evidenceCard(e){const href=safeLink(e.url),has=Boolean(e.excerpt);return `<article class="ev194"><div class="mini194"><b>${esc(e.publisher||e.source_assessment?.publisher||'來源未標示')}</b><span>${esc(e.published_at||'日期未取得')}</span><em>${has?'有前言／節錄':'僅標題'}</em></div><h3>${href?`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(e.title)} ↗</a>`:esc(e.title)}</h3>${has?`<blockquote>${esc(e.excerpt)}</blockquote>`:''}<p class="sub194">${esc(e.content_reason||'此份快照沒有記錄擷取原因')}。${esc(e.rights_scope||'使用權未另行確認')}</p><p class="sub194">證據取得：${esc(e.fetched_at||e.available_at||'未記錄')}；不是整篇文章已核實。</p>${e.relation_assessment?`<p class="warn194">${esc(e.relation_assessment.reason)}</p>`:''}${e.current_analysis_mode?`<details><summary>本次規則分析，不改寫舊分數</summary><p>事件分 ${num(e.impact_score)}，${esc(e.analysis_engine)}；非報酬率</p><p>${esc(e.summary)}</p><p>驗證：${esc(e.confirmation)}</p><p>失效：${esc(e.invalidation)}</p><small>${esc(e.current_analysis_mode)}</small></details>`:''}</article>`}
export function statusClass(d){return ['falling','stale','missing','corporate_action'].includes(d?.state)?'red194':['stabilizing','reclaim'].includes(d?.state)?'teal194':'amber194'}
export function downsideHTML(d={},name='個股'){
 const m=d.metrics||{},lv=d.research_levels||{};
 return `<div class="down194 ${statusClass(d)}"><span class="ey194">${esc(name)} · ${esc(d.price_date||'缺價格日期')}</span><h2>${esc(d.label||'尚未產生下跌研究')}</h2><p>${esc(d.reason||'請執行資料更新')}</p><div class="metric194"><div><small>5日變化</small><b>${num(m.return_5d_pct)}%</b></div><div><small>距窗口高點</small><b>${num(m.drawdown_from_60high_pct)}%</b></div><div><small>RSI 14</small><b>${num(m.rsi14,1)}</b></div><div><small>成交量／前20日均量</small><b>${num(m.volume_ratio_prior20)}倍</b></div></div><p class="warn194"><strong>不是低點機率：</strong> ${esc(d.next_step||'先補齊資料')}</p>${d.checks?.length?`<div class="check194">${d.checks.map(x=>`<div><b class="${x.status==='pass'?'ok194':x.status==='fail'?'no194':'miss194'}">${x.status==='pass'?'達到':x.status==='fail'?'未達':'缺資料'}</b><span><strong>${esc(x.label)}</strong><small>${esc(x.evidence)}</small></span></div>`).join('')}</div>`:''}${Object.keys(lv).length?`<div class="metric194"><div><small>下期確認參考上方</small><b>${num(lv.next_session_confirmation_above)}</b></div><div><small>停止情境下方</small><b>${num(lv.invalidation_below)}</b></div><div><small>20日壓力情境</small><b>${num(lv.pressure_scenario)}</b></div><div><small>現價毛報酬／風險</small><b>${num(lv.gross_reward_risk)}</b></div></div>`:''}<p class="sub194">${esc(d.add_plan?.label||'沒有可用加碼研究')}。不改原策略、不改已確認試單。缺基本／估值仍保留缺口；價格跌深不是便宜保證。</p></div>`
}
export function bridgeHTML(payload,context){
 if(context?.mode!=='forward')return '<h2>市場與止跌研究</h2><p>歷史／合成模式不載入今日後續消息，避免偷看未來。</p>';
 if(!payload)return '<h2>市場與止跌研究尚未建立</h2><p>執行 Actions → Update evidence and downside research (no Qwen)。不必重新訓練。</p><a href="market-watch.html">打開資料與錯誤診斷 →</a>';
 if(payload.source_snapshot_sha256!==context.hash)return '<h2>新市場附檔尚未對上這份快照</h2><p>沒有把不同來源時間拼成同一份原分析。</p><a href="market-watch.html">另開目前市場研究（不改原批次） →</a>';
 const d=payload.market||{},c=payload.collection||{};
 return `<span class="ey194">市場風險另計，不把所有公司都判成財報利空</span><h2>${esc(d.label||'未計算')}</h2><p>${esc(d.reason||'價格尚未取得')}</p><p>市場價格 ${esc(d.price_date)}；證據更新 ${esc(payload.generated_at)}；背景新聞 ${(payload.market_events||[]).length}則，來源RSS有前言 ${num(c.rss_with_intro,0)}則。</p><p class="sub194">原快照仍為 ${esc(payload.source_snapshot_at)}；以下為較新的獨立研究，不冒稱原Qwen重跑。</p><a class="button" href="market-watch.html">看下跌原因、止跌條件與逐則前言 →</a>${(payload.market_events||[]).slice(0,3).map(evidenceCard).join('')}`
}
export function sizeAddition(x){
 const vals=['entry','stop','target','cash','cap','risk','held','mark','fraction'].map(k=>Number(x[k]));
 if(vals.some(v=>!Number.isFinite(v)||v<0))return {shares:0,reason:'請輸入有效非負數字'};
 const [entry,stop,target,cash,cap,risk,held,mark,fraction]=vals;
 if(!(stop>0&&entry>stop&&target>entry&&fraction<=1&&Number.isInteger(held)))return {shares:0,reason:'須為0 < 停止價 < 進場價 < 目標情境'};
 const fee=a=>Math.max(20,a*.001425),slip=.001,tax=.003;
 const existing=held?Math.max(0,held*mark-(held*stop*(1-slip)*(1-tax)-fee(held*stop*(1-slip)))):0;
 const remaining=Math.max(0,risk-existing),riskCap=Math.min(remaining,risk*fraction),cashCap=Math.max(0,Math.min(cash,cap-held*mark));
 function outcome(q,price){const buy=q*entry*(1+slip),sell=q*price*(1-slip);return {buy:buy+fee(buy),net:sell-fee(sell)-sell*tax}}
 let lo=0,hi=Math.floor(cashCap/entry);
 while(lo<hi){const q=Math.floor((lo+hi+1)/2),o=outcome(q,stop);if(o.buy<=cashCap&&o.buy-o.net<=riskCap)lo=q;else hi=q-1}
 if(!lo)return {shares:0,existingRisk:existing,remaining,reason:'既有部位、費用與分段風險扣除後，無一股空間'};
 const loss=outcome(lo,stop),gain=outcome(lo,target);
 if(gain.net-gain.buy<=0||(gain.net-gain.buy)/(loss.buy-loss.net)<1.5)return {shares:0,riskLimitedShares:lo,existingRisk:existing,remaining,reason:'含成本後報酬／風險不足1.5研究門檻，不強迫加碼'};
 return {shares:lo,existingRisk:existing,remaining,buy:loss.buy,loss:loss.buy-loss.net,profit:gain.net-gain.buy,
  rr:(gain.net-gain.buy)/(loss.buy-loss.net),expectedReturn:null,autoOrders:false};
}
