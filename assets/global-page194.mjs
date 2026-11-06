import {esc,num} from './downside194.mjs';
import {marketTile,eventCard,stockGlobalHTML,relationshipsHTML} from './global194.mjs';
const $=id=>document.getElementById(id);let data;
function riskHTML(d){const r=d.risk||{},n=d.coverage||{};return `<div class="g-riskbox"><div><h3>${esc(r.label)}</h3><p>可比較地區：${esc(r.coverage_regions?.join(' / ')||'不足')}；達到壓力門檻：${esc(r.stressed_regions?.join(' / ')||'尚未觸發或資料不足')}</p><p>${esc(r.rules)}</p><p><b>不是底部機率，不是市場方向預測。</b> ${esc(r.limitation)}</p></div><div class="g-riskstats"><div><small>市場數據覆蓋</small><b>${n.market_usable??0} / ${n.market_total??0}</b></div><div><small>新加碼風險乘數</small><b>${r.new_risk_multiplier===null?'待資料':num(r.new_risk_multiplier,2)+'×'}</b></div><div><small>有來源事件</small><b>${n.events??0}</b></div><div><small>Qwen新增呼叫</small><b>0</b></div></div></div>`}
async function load(){
 try{
  const r=await fetch('data/global194/latest.json?t='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(25000)});
  if(!r.ok)throw Error(`全球附檔未建立（HTTP ${r.status}）。執行 Update evidence and downside research (no Qwen)，等Pages部署後重讀。`);
  data=await r.json();$('globalError').hidden=true;$('globalDemo').hidden=!data.demo;
  $('globalStamp').textContent=`全球觀測：${data.generated_at} ｜ 原台股快照：${data.source_snapshot_at} ｜ 不回填原分數／歷史`;
  $('globalRisk').innerHTML=riskHTML(data);
  $('equityTiles').innerHTML=data.markets.filter(x=>x.kind==='equity').map(marketTile).join('');
  $('otherTiles').innerHTML=data.markets.filter(x=>!['equity','fx'].includes(x.kind)).map(marketTile).join('');
  $('fxTiles').innerHTML=data.markets.filter(x=>x.kind==='fx').map(marketTile).join('');
  $('crosses').innerHTML=(data.currency_crosses||[]).map(x=>`<div>台幣相對${esc(x.other_currency)}・5共同觀測期<b>${num(x.twd_appreciation_5d_pct)}%</b>${esc(x.interpretation||x.reason)}<small><br>${esc(x.date||'未取得')} · ${esc(x.status)}</small></div>`).join('');
  $('policyCards').innerHTML=(data.policy_events||[]).slice(0,8).map(eventCard).join('')||'<p class="g-warning">未取得符合期間的選舉／政策線索，不編造政策消息。</p>';
  $('globalPaths').innerHTML=relationshipsHTML(data);
  $('globalNews').innerHTML=(data.events||[]).filter(e=>e.policy_stage==='none').slice(0,12).map(eventCard).join('');
  const prev=$('globalStock').value;$('globalStock').innerHTML=(data.stock_exposures||[]).map(s=>`<option value="${esc(s.symbol)}">${esc(s.name)} · ${esc(s.symbol)}</option>`).join('');
  if(data.stock_exposures?.some(s=>s.symbol===prev))$('globalStock').value=prev;showStock();
  const c=data.collection||{};
  $('globalHealth').innerHTML=`<p>本輪市場請求 ${num(c.quote_requests,0)} / ${num(c.quote_limit,0)}；RSS ${num(c.news_requests,0)} / ${num(c.news_limit,0)}。新Qwen呼叫0。不下載模型。</p><p>${esc(c.coverage_note)}</p><p class="g-warning">美國與亞洲同日收盤不同時；日內反轉可能使新聞與最新日頻資料不一致。利率用bp、匯率用本幣方向，缺資料不當成0變化。尚未涵蓋每個市場假日與臨時休市。</p><div class="g-health">${(c.sources||[]).map(s=>`<details><summary>${esc(s.key)} · ${esc(s.state)}</summary><p>觀測 ${esc(s.observed_at||s.cached_observed_at||'沒有')} · 筆數 ${num(s.rows,0)}</p><p>${esc(s.error||'沒有新增錯誤')}</p></details>`).join('')}</div>`;
 }catch(e){$('globalError').hidden=false;$('globalError').textContent=e.message;}
}
function showStock(){const symbol=$('globalStock').value;$('globalExposure').innerHTML=stockGlobalHTML(data,symbol);$('toSizing').href='market-watch.html#'+encodeURIComponent(symbol)}
$('globalStock').onchange=showStock;$('refreshGlobal').onclick=load;await load();
