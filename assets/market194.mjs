import {constrainSizing,globalBridge} from './global194.mjs?v=1934g1';
import {esc,num,evidenceCard,downsideHTML,sizeAddition} from './downside194.mjs';
const $=id=>document.getElementById(id);let data=null,stock=null,globalData194=null;
async function load(){try{
 const response=await fetch('data/context194/latest.json?t='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(20000)});
 if(!response.ok)throw Error('尚無新研究附檔（HTTP '+response.status+'）。先在Actions執行 Update evidence and downside research (no Qwen)。不用開GPU。');
 data=await response.json();globalData194=null;
 try{const gr=await fetch('data/global194/latest.json?t='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(20000)});if(gr.ok)globalData194=await gr.json()}catch{}
 $('globalSizingStatus194').innerHTML=globalBridge(globalData194,{mode:'forward',hash:data.source_snapshot_sha256});
 $('error').hidden=true;$('demo').hidden=!data.demo;
 $('asof').textContent='研究附檔：'+data.generated_at+' ｜ 原新聞快照：'+data.source_snapshot_at+' ｜ 兩者時間分開，不回填歷史';
 $('marketState').innerHTML=downsideHTML(data.market,data.market?.name||'市場基準');$('chart').innerHTML=chart(data.market_candles||[]);
 $('marketNotes').innerHTML=`<p>${esc(data.market?.price_source)}</p><p class="sub194">${esc(data.market?.breadth_status)}</p><p class="warn194">當下只能辨識風險與止跌條件，不能證明最低點已經過去。反彈、長下影線和低RSI都不是單獨的買進理由。</p>`;
 $('paths').innerHTML=(data.pathways||[]).map(p=>`<article class="path194"><span>${esc(p.title)}</span><div><p>${esc(p.chain)}</p><small>${esc(p.basis)}</small><small>待核對：${esc(p.needs_verification)}</small><small>報導來源名稱 ${p.distinct_publishers} 個，不代表獨立確認 ${p.distinct_publishers} 次。</small></div></article>`).join('')||'<p class="warn194">尚未取得可用大盤／產業報導，不編造下跌原因。下方可查看來源失敗紀錄。</p>';
 $('marketNews').innerHTML=(data.market_events||[]).slice(0,12).map(evidenceCard).join('');
 const before=$('symbol').value||decodeURIComponent(location.hash.replace('#',''));
 $('symbol').innerHTML=(data.stocks||[]).map(s=>`<option value="${esc(s.symbol)}">${esc(s.name)} · ${esc(s.symbol)}</option>`).join('');
 if(data.stocks.some(s=>s.symbol===before))$('symbol').value=before;
 showStock();
 const c=data.collection||{};$('sourceHealth').innerHTML=`<p>背景RSS取得 ${num(c.rss_items,0)} 則，其中 ${num(c.rss_with_intro,0)} 則有來源前言。本次外部RSS請求 ${num(c.requests,0)}；授權文章嘗試 ${num(c.article_attempts,0)}；Qwen新呼叫 0。</p>`+(c.sources||[]).map(x=>`<div class="health194"><strong>${esc(x.source||'資料源')}：${esc(x.status)}</strong><small>有效筆數 ${num(x.items,0)}；觀測 ${esc(x.observed_at||'未取得')} ${esc(x.error||'')}</small></div>`).join('')+(data.errors||[]).map(x=>`<p class="warn194">${esc(x)}</p>`).join('');
 }catch(e){$('error').textContent=e.message;$('error').hidden=false;}}
function showStock(){stock=data?.stocks.find(s=>s.symbol===$('symbol').value);if(!stock)return;
 $('stockState').innerHTML=downsideHTML(stock.downside,stock.name);
 const l=stock.downside.research_levels||{};$('entry').value=l.reference_price??'';$('stop').value=l.invalidation_below??'';$('target').value=l.pressure_scenario??'';
 $('sizingResult').textContent='設定僅用於目前價位的獨立虛擬情境；不提交交易。';
 const events=[...(stock.events||[]),...(stock.context_events||[])];const seen=new Set;
 $('stockNews').innerHTML=events.filter(e=>{const k=e.id||e.url;if(seen.has(k))return false;seen.add(k);return true}).slice(0,14).map(evidenceCard).join('')||'<p class="warn194">沒有取得公司事件／相關市場資料。價格診斷仍可使用，但不能宣稱公司基本面已改善。</p>';
 history.replaceState(null,'','#'+encodeURIComponent(stock.symbol));}
function chart(rows){rows=rows.slice(-60);if(rows.length<2)return '<p class="warn194">沒有足夠同口徑價格，不畫假走勢。</p>';
 const vals=rows.map(x=>x.close),lo=Math.min(...vals),hi=Math.max(...vals),w=570,h=255;
 const y=v=>h-30-(v-lo)/Math.max(1,hi-lo)*(h-60),x=i=>45+i/(rows.length-1)*(w-65);
 const points=vals.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
 return `<svg viewBox="0 0 ${w} ${h+35}" role="img" aria-label="截至資料日期的收盤曲線"><line x1="45" y1="25" x2="45" y2="${h-25}" stroke="#bfd4db"/><line x1="45" y1="${h-25}" x2="${w-20}" y2="${h-25}" stroke="#bfd4db"/><polyline points="${points}" fill="none" stroke="#0a8480" stroke-width="3"/><text x="3" y="30" font-size="11" fill="#57717d">${esc(num(hi,0))}</text><text x="3" y="${h-25}" font-size="11" fill="#57717d">${esc(num(lo,0))}</text><text x="45" y="${h+6}" font-size="12" fill="#57717d">${esc(rows[0].date)}</text><text x="${w-105}" y="${h+6}" font-size="12" fill="#57717d">${esc(rows.at(-1).date)}</text></svg>`;}
$('refresh').onclick=load;$('symbol').onchange=showStock;
$('sizing').onsubmit=e=>{e.preventDefault();if(!stock)return;
 const d=stock.downside;
 if(stock.sector==='ETF'||/^00[0-9]+\.TW$/.test(stock.symbol)){$('sizingResult').textContent='此情境計算器使用普通股票費用假設。ETF請到原PaperLab使用對應商品費用，不混用稅率。';return;}
 if(!d.research_stage){$('sizingResult').textContent='本組止跌條件未通過：不新增股數。'+d.next_step;return;}
 const at=Date.parse(data.generated_at);
 if(!Number.isFinite(at)||Date.now()-at>36*3600000||at-Date.now()>300000){$('sizingResult').textContent='研究附檔已超過36小時或時間晚於目前裝置，先核對時鐘及更新行情；不延用錯誤時點給加碼股數。';return;}
 const x={};for(const k of ['entry','stop','target','cash','cap','risk','held'])x[k]=Number($(k).value);
 x.mark=d.metrics.close;x.fraction=d.risk_budget_fraction_for_research;
 if(!Number.isInteger(x.held)){$('sizingResult').textContent='既有股數需為非負整數';return;}
 let extra='';
 if($('useGlobal194').checked){if(globalData194?.source_snapshot_sha256!==data.source_snapshot_sha256){$('sizingResult').textContent='全球資料與個股快照不同，先更新，不合併錯誤時點。';return;}const applied=constrainSizing(x,globalData194);if(!applied.ok){$('sizingResult').textContent=applied.reason;return;}x.fraction=applied.input.fraction;extra=` 全球研究乘數${applied.multiplier}×（未校準），原個股條件仍須通過。`;}
 const result=sizeAddition(x);
 $('sizingResult').textContent=result.shares?`獨立情境 ${result.shares} 股；支出 ${num(result.buy)} 元；停止情境損失 ${num(result.loss)} 元；到壓力情境淨利 ${num(result.profit)} 元；成本後比率 ${num(result.rr)}。不是預期收益，也沒有送出試單。`:`新增0股：${result.reason}。既有風險 ${num(result.existingRisk)} 元。`;
 $('sizingResult').textContent+=extra;
};
await load();
