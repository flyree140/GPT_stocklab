// Global research is distinct from locked news snapshots and saved paper trades.
import {esc,num,safeLink} from './downside194.mjs';
export function riskMultiplier(payload,now=Date.now()){
 if(payload?.demo)return null;
 const at=Date.parse(payload?.generated_at||'');
 if(!Number.isFinite(at)||at>now+300000||now-at>36*3600000)return null;
 const r=payload?.risk;
 if(!r?.coverage_valid||!Number.isFinite(r.new_risk_multiplier))return null;
 return Math.min(1,Math.max(0,r.new_risk_multiplier));
}
export function constrainSizing(input,payload,now=Date.now()){
 const m=riskMultiplier(payload,now);
 if(m===null)return {ok:false,reason:'全球核心市場資料不足、時間過期或未核對，無法比較全球風險版本。原個股研究仍保留，不自動當看空。'};
 return {ok:true,input:{...input,fraction:Math.min(Number(input.fraction),Number(input.fraction)*m)},multiplier:m,
  reason:'原個股風險比例 × 全球研究乘數；不是資金比例、預測報酬或已校準最佳參數。'};
}
const stateLabel={recent:'最近完整觀測',lagged:'日期落後／休市待核',stale:'過期',missing:'未取得'};
export function marketTile(m){
 const fx=m.kind==='fx',yield_=m.kind==='yield';
 const value=yield_?m.change_1d_bp:fx?m.local_appreciation_1d_pct:m.change_1d_pct;
 const unit=yield_?'bp':fx?'%（本幣兌美元）':'%';
 const direction=value===null||value===undefined?'未取得':`${value>0?'+':''}${num(value,2)}${unit}`;
 const tone=value===null||value===undefined?'missing':value<0?'negative':'positive';
 const source=safeLink(m.source_url);
 return `<article class="g-tile"><div class="g-tile-head"><span>${esc(m.region)}</span><small>${esc(stateLabel[m.status]||m.status)}</small></div><h3>${esc(m.label)}</h3><div class="g-value">${num(m.last,m.kind==='fx'?4:2)}${yield_?'%':''}</div><strong class="g-change ${tone}">${esc(direction)}</strong><p>${fx?esc(m.direction_label||'匯率方向待資料'):'5個觀測期 '+(yield_?num(m.change_5d_bp)+' bp':num(m.change_5d_pct)+'%')}</p><p class="g-small">${fx?'報價＝1美元換幾單位本幣，數字升≠本幣升。':''}${m.roll_warning?'近月期貨，有換月影響；不等於現貨。':''}</p><div class="g-time"><span>資料日 ${esc(m.price_date||'未取得')}</span><span>觀測 ${esc(m.observed_at||'未取得')}</span></div>${source?`<a href="${esc(source)}" target="_blank" rel="noopener">來源 ↗</a>`:''}</article>`;
}
export function eventCard(e){const url=safeLink(e.url);return `<article class="g-event"><div class="g-tags"><span>${esc(e.publisher)}</span><span>${esc(e.published_at)}</span><span>${e.excerpt?'RSS前言':'只有標題'}</span></div><h3>${url?`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(e.title)} ↗</a>`:esc(e.title)}</h3>${e.excerpt?`<blockquote>${esc(e.excerpt)}</blockquote>`:''}${e.policy_stage!=='none'?`<b class="g-stage">${esc(e.policy_stage_label)}</b>`:''}<p>${esc(e.next_check)}</p><small>首次觀測 ${esc(e.available_at)} · 法律效力未自動核實 · 不表示已核實所有報導</small></article>`}
export function globalBridge(payload,context){
 if(context?.mode!=='forward')return '<h3>全球研究保留時點</h3><p>歷史／合成試驗不載入今天的全球消息，避免偷看未來。</p>';
 if(payload?.demo)return '<h3>全球資料為合成驗收案例</h3><p>不套入正式試單或歷史；僅供介面測試。</p><a href="global-watch.html">查看合成示範頁 →</a>';
 if(!payload)return '<h3>全球連動研究尚未取得</h3><p>執行既有證據／下跌更新，會連同全球資料更新。</p><a href="global-watch.html">全球市場、匯率與政策 →</a>';
 if(payload.source_snapshot_sha256!==context.hash)return '<h3>全球研究與這份快照不同時點</h3><p>不將新消息偷偷寫回舊評分。</p><a href="global-watch.html">另看目前全球研究 →</a>';
 return `<div class="g-bridge"><b>全球連動｜${esc(payload.risk?.label)}</b><p>${payload.coverage?.market_usable||0}/${payload.coverage?.market_total||0}個市場可用 · 新聞${payload.coverage?.events||0}則 · ${esc(payload.generated_at)}</p><p>匯率按報價方向與時區分開；選舉結果不等於法規生效。不改已確認試單。</p><a href="global-watch.html">看全球 → 產業 → 個股 → 風險傳導 →</a></div>`;
}
export function stockGlobalHTML(payload,symbol){
 const s=payload?.stock_exposures?.find(x=>x.symbol===symbol);
 if(!s)return '<p>尚無這檔的全球曝險研究；不推估收入或客戶占比。</p>';
 return `<h3>${esc(s.name)}：不能把所有全球利空直接扣成EPS衰退</h3><div class="g-exposures">${(s.channels||[]).map(c=>`<article><span class="g-badge">${esc(c.relation)}</span><h4>${esc(c.title)}</h4><p>${esc(c.mechanism)}</p><p class="g-warning">還缺：${esc(c.missing)}</p><small>對公司淨方向：未知／混合，不自動改原分數</small></article>`).join('')}</div><p>${esc(s.warning)}</p><p>已核對曝險文件：${s.reviewed_exposure_documents?.length||0}份（有文件也不代表已量化淨曝險）</p>`;
}
export function relationshipsHTML(payload){return (payload?.pathways||[]).map(p=>`<article class="g-path"><div><b>${esc(p.title)}</b><span>${esc(p.evidence_status)}</span></div><div><p>${esc(p.chain)}</p><small>${esc(p.basis)} · ${esc(p.gap)}</small><small>報導線索${p.event_ids.length}筆；不是獨立確認次數</small></div></article>`).join('')}
export function applyGlobalSettings(settings,payload,ctx,now=Date.now(),payloadHash=null){
 if(ctx?.mode!=='forward')throw Error('全球風險組只適用目前向前研究；歷史試驗不可使用今日消息。');
 if(!payload||payload.source_snapshot_sha256!==ctx.hash)throw Error('全球研究與原快照雜湊不同，先更新；不當成市場看空。');
 const m=riskMultiplier(payload,now);
 if(m===null)throw Error('全球研究過期或核心市場未齊；本組暫無可確認試單，可關閉此組保留原規則作對照。');
 if(!Number.isFinite(settings.maxLoss)||settings.maxLoss<=0)throw Error('原風險金額無效');
 return {...settings,maxLoss:Math.floor(settings.maxLoss*m*100)/100,global194:{
  version:payload.version,source_snapshot_sha256:payload.source_snapshot_sha256,
  generated_at:payload.generated_at,payload_sha256:payloadHash,
  regime:payload.risk.code,multiplier:m,original_maxLoss:settings.maxLoss,
  rules_version:payload.rules_version,coverage_regions:payload.risk.coverage_regions,
  note:'額外全球研究組；只縮減新增風險，不改原分數，不代表已校準或可預測下跌。'}};
}
