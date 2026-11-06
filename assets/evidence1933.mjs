// Read-only observability. Never changes original labels, hashes, budgets or orders.
const esc=v=>String(v??'未記錄').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=v=>Number.isFinite(v)?v.toLocaleString('zh-TW',{maximumFractionDigits:2}):'未記錄';
const names={data_block:'資料／行情缺口',label_gate:'原標籤門檻',execution_constraint:'價格／資金／風險限制',research_rejection:'研究規則拒絕',other_block:'其他待核對'};
export function classifyBlock(v){const s=String(v);if(/原標籤不是條件式買入/.test(s))return 'label_gate';if(/資料|行情|日曆|缺|過期|fetch|404/.test(s))return 'data_block';if(/資金|現金|預算|風險|費用|股數|限價|報酬|虧損/.test(s))return 'execution_constraint';if(/避開|分數低|低於50|偏弱/.test(s))return 'research_rejection';return 'other_block';}
export function modelFacts(s={},r={}){const p=s.news_pipeline||{},q=p.qwen||{},m=r.model_status||{};
 return {attempts:p.qwen_reserved_this_run??s.qwen_used??null,valid:q.validated_results??null,cache:s.qwen_cache_hits??q.cache_hits??null,
  ownRequested:m.enabled_requested??null,ownAttempts:m.attempts_this_run??null,ownValid:Array.isArray(r.stocks)?r.stocks.reduce((t,x)=>t+(x.analyses?.length||0),0):null,
  ownCache:m.cache_hits??null,ownStatus:m.result||'沒有對應同快照的狀態',revision:m.adapter_revision||null};}
export function summarize(s={},r={},rows=[]){const facts=modelFacts(s,r);let counts={};for(const row of rows){const keys=new Set((row.proposal?.blocks||[]).map(classifyBlock));for(const k of keys)counts[k]=(counts[k]||0)+1;}
 const news=(s.stocks||[]).flatMap(x=>x.news||[]);return {facts,counts,news:news.length,included:news.filter(x=>x.included===true).length,
   evidenceHints:news.filter(x=>!!x.model_evidence).length,eligible:rows.filter(x=>x.eligible).length,observations:rows.length};}
function field(k,v){return `<div class="e1933-tile"><small>${esc(k)}</small><b>${esc(v)}</b></div>`;}
export function panelHTML(s,r,rows,{issue='',strategy='candidate'}={}){const d=summarize(s,r,rows),f=d.facts;return `
 <div class="eyebrow">EVIDENCE · 這份快照實際使用了什麼？</div><h2>新聞、Qwen與未買原因</h2>
 <p class="note"><b>沒有買進不等於預測下跌。</b> 此區不改分、不放寬條件、不建立買單。原標籤／資料缺失／真正研究拒絕分開看。</p>
 <div class="e1933-grid">${field('快照時間',s.generated_at||'未讀取')}${field('新聞數／納入CPU計分',d.news+' / '+d.included)}${field('原Qwen嘗試／有效輸出（含快取）',n(f.attempts)+' / '+n(f.valid))}${field('原Qwen快取／有證據提示新聞',n(f.cache)+' / '+d.evidenceHints)}${field('自有adapter嘗試／有效輸出',n(f.ownAttempts)+' / '+n(f.ownValid))}${field('自有adapter是否要求啟用',f.ownRequested===null?'未記錄':f.ownRequested?'是；仍須看結果':'否')}</div>
 <p class="muted">嘗試 ≠ 成功；未記錄 ≠ 0。配置／結算按鈕不呼叫Qwen。數值來自這份研究快照，不是你帳號的即時用量。</p>
 <p><b>自有權重狀態：</b>${esc(f.ownStatus)}<small class="e1933-wrap">${esc(f.revision||'尚無可核對的adapter revision')}</small></p>
 ${issue?`<p class="note">${esc(issue)}。未把不同時點的adapter答案拼進來。</p>`:''}
 <p><b>誰決定分數？</b> 新聞分數與原買進標籤由CPU規則產生；原Qwen只可提供分類／證據提示。自己的LoRA是影子研究，目前不改寫原分數或股數。</p>
 <div class="e1933-grid">${Object.entries(d.counts).map(([k,v])=>field(names[k],v+' 檔')).join('')||field('本次阻擋原因','沒有可列出原因／尚未重算')}</div>
 <p class="muted">同一檔可能有多種原因，不能直接相加。研究規則拒絕也不是已校準的下跌機率。</p>
 <p><b>現在這組在測什麼？</b> ${strategy==='original'?'忠實原建議組：只有原標籤 conditional_buy 才建單；0筆時只保存觀察，日結不會自動替你買。':'候選探索組：測固定候選／價格／風險規則，不冒充原系統已叫你買進。'} 全部股票的1／5／10／20日對照在「全部分析驗證」，含未建單者。</p>
 <details><summary>Qwen沒有有效輸出時，先查這些，不要先花GPU重訓</summary><ol><li>每日工作流程的 skip_qwen 是否勾選？它的手動預設是勾選。</li><li>啟用自有權重後，是否配置同版基底、adapter repo、固定revision及HF讀取權限？</li><li>工作流程日誌是停用、預算用完、模型失敗、快取命中，還是JSON／原文證據被拒絕？</li><li>data/research192/latest.json 是否屬於同一快照？新附檔不會改寫舊歷史。</li><li>標題不是全文；沒核對原公告，就不能把它說成已核實。</li></ol></details>`;}
function link194(u){try{const x=new URL(u);return ['https:','http:'].includes(x.protocol)?x.href:''}catch{return ''}}
function evidence(e){if(Array.isArray(e))return e.map(x=>x.quote||x.text||'').filter(Boolean).join('；');return typeof e==='string'?e:e?.quote||e?.text||'';}
export function stockEvidenceHTML(stock={},extra={}){const news=stock.news||[],own=extra.analyses||[];return `<section class="e1933-stock"><h2>逐則新聞分數與模型證據</h2><p class="muted">下列原始分數來自保存快照，不是本次重新生成，也不是上漲機率。沒有分數／引文就顯示未記錄。</p>${news.map(e=>`<article class="factor"><div class="e1933-grid">${field('事件影響分',n(e.impact_score))}${field('本次有效分',n(e.active_score))}${field('納入研究',e.included===true?'是':e.included===false?'否':'未記錄')}</div><h3>${esc(e.title)}</h3>${link194(e.url)?`<a href="${esc(link194(e.url))}" target="_blank" rel="noopener">原文來源 ↗</a>`:''}${e.excerpt?`<blockquote>${esc(e.excerpt)}</blockquote>`:`<p class="note">內容缺口：${esc(e.content_reason||'這份舊快照沒有保存前言或內文；新程式不會改寫歷史。重跑每日研究後才產生新證據。')}</p>`}<p>引擎：${esc(e.analysis_engine||'未記錄，不能宣稱Qwen已分析')}</p><p>證據層級：${esc(e.source_assessment?.coverage||'未記錄')}；原始文件核對：${e.source_assessment?.verified===true?'已記錄核對':'未核對'}</p><p>原Qwen證據提示：${esc(evidence(e.model_evidence)||'沒有保存有效模型提示')}</p><p>傳導：${esc(e.summary||e.mechanism||'未記錄')}</p><p>確認：${esc(e.confirmation||'未記錄')}<br>失效：${esc(e.invalidation||'未記錄')}</p><details><summary>分數構成／來源欄位（不可由高分推論高報酬）</summary><pre>${esc(JSON.stringify({id:e.id,published_at:e.published_at,available_at:e.available_at,score_breakdown:e.score_breakdown??null,metrics:e.metrics??[],flags:e.flags??[],model_evidence:e.model_evidence??null},null,2))}</pre></details></article>`).join('')||'<p class="note">此快照沒有新聞資料；不是「模型認定沒有影響」。</p>'}<h3>自己的LoRA：有效輸出 ${own.length} 筆（影子，未進入原評分）</h3>${own.map(a=>`<details class="factor"><summary>${esc(a.id)} · 點開完整輸出與原文引用</summary><pre>${esc(JSON.stringify({revision:a.model_revision,output:a.output,changes_original_score:false},null,2))}</pre></details>`).join('')}<p class="note">原模型、你自己的權重、規則與股數計算是不同階段。要聲稱改進，須用相同事件、同一成本規則及未見日期對照，不能只看這三天下跌且沒買。</p></section>`;}
