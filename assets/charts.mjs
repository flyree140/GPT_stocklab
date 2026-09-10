/** Local SVG financial charts. No CDN, iframe, remote tracking or chart license key. */
import {esc,num} from './engine.mjs';
const fmt=(x,d=1)=>num(x)===null?'—':Number(x).toLocaleString('zh-TW',{maximumFractionDigits:d,minimumFractionDigits:d});
const line=(arr,x,y)=>arr.map((r,i)=>num(r.value)===null?'':`${i&&num(arr[i-1].value)!==null?'L':'M'}${x(i).toFixed(2)},${y(r.value).toFixed(2)}`).join(' ');
export function spark(values,w=130,h=30){
 const valid=values.filter(x=>num(x)!==null);if(valid.length<2)return '';
 const a=Math.min(...valid),b=Math.max(...valid),y=v=>h-3-(v-a)/(b-a||1)*(h-6),x=i=>3+i*(w-6)/(values.length-1);
 return `<svg viewBox="0 0 ${w} ${h}" aria-label="近期收盤走勢"><path d="${line(values.map(value=>({value})),x,y)}" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>`;
}
export function candles(el,all,{count=60,end=null,indicator='rsi',events=[],convention='tw',onHover=()=>{}}={}){
 const rows=all.slice(0,end||all.length).slice(-count);
 if(!rows.length){el.innerHTML='<div class="empty">沒有可用日 K；不使用假價格補圖。</div>';return;}
 const W=960,H=426,L=18,R=78,top=22,P=222,Vtop=276,VH=45,Itop=348,IH=43,base=405,N=rows.length;
 const low=Math.min(...rows.map(r=>r.low)),high=Math.max(...rows.map(r=>r.high));const pad=(high-low)*.07||1;
 const y=v=>top+P-(v-(low-pad))/(high-low+pad*2)*P;const x=i=>L+(i+.5)*(W-L-R)/N;const step=(W-L-R)/N;
 const vmax=Math.max(...rows.map(r=>num(r.volume,0)),1);const up=convention==='tw'?'#bb485b':'#208377',down=convention==='tw'?'#208377':'#bb485b';
 let g='';
 for(let j=0;j<5;j++){const v=low-pad+(high-low+pad*2)*j/4,yy=y(v);g+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="#e4eaec" stroke-width="1"/><text x="${W-R+14}" y="${yy+4}" class="axis">${fmt(v,1)}</text>`;}
 rows.forEach((r,i)=>{const c=r.close>=r.open?up:down,body=Math.abs(y(r.close)-y(r.open));g+=`<line x1="${x(i)}" x2="${x(i)}" y1="${y(r.high)}" y2="${y(r.low)}" stroke="${c}" stroke-width="1.2"/><rect x="${x(i)-step*.30}" y="${Math.min(y(r.open),y(r.close))}" width="${Math.max(1,step*.6)}" height="${Math.max(1,body)}" fill="${c}"/><rect x="${x(i)-step*.30}" y="${Vtop+VH-(r.volume||0)/vmax*VH}" width="${Math.max(1,step*.6)}" height="${(r.volume||0)/vmax*VH}" fill="${c}" opacity=".42"/>`;});
 for(const [key,col] of [['ma5','#c99f50'],['ma20','#297e91'],['ma60','#8083ad']]){g+=`<path d="${line(rows.map(r=>({value:r[key]})),x,y)}" fill="none" stroke="${col}" stroke-width="1.6"/>`;}
 g+=`<text x="${L}" y="${Vtop-10}" class="axis">成交量</text><text x="${W-R+14}" y="${Vtop+10}" class="axis">${fmt(vmax/1e6,1)}M</text>`;
 const fields=indicator==='kd'?['k','d']:indicator==='macd'?['macd','signal']:['rsi'];const vals=rows.flatMap(r=>fields.map(k=>num(r[k]))).filter(v=>v!==null);
 let iMin=indicator==='macd'?Math.min(...vals,0):0,iMax=indicator==='macd'?Math.max(...vals,0):100;
 const iy=v=>Itop+IH-(v-iMin)/(iMax-iMin||1)*IH;
 g+=`<text x="${L}" y="${Itop-8}" class="axis">${indicator.toUpperCase()}</text>`;
 for(const level of indicator==='macd'?[0]:[30,70])g+=`<line x1="${L}" x2="${W-R}" y1="${iy(level)}" y2="${iy(level)}" stroke="#d8e3e7" stroke-dasharray="4 5"/>`;
 fields.forEach((k,i)=>{g+=`<path d="${line(rows.map(r=>({value:r[k]})),x,iy)}" fill="none" stroke="${i?'#aa926d':'#168c83'}" stroke-width="1.7"/>`;});
 for(let j=0;j<5;j++){const i=Math.round((N-1)*j/4);g+=`<text x="${x(i)}" y="${base+11}" text-anchor="middle" class="axis">${rows[i].date.slice(5)}</text>`;}
 const unique=new Set();for(const e of events){const d=e.published_at?.slice(0,10),i=rows.findIndex(r=>r.date===d);if(i<0||unique.has(d)||!e.included)continue;unique.add(d);g+=`<circle cx="${x(i)}" cy="${y(rows[i].low)+12}" r="5.5" fill="#dba94c" stroke="#fff" stroke-width="2"><title>${esc(e.category_label)}：${esc(e.title)}</title></circle>`;}
 el.innerHTML=`<svg class="financial-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="日 K、均線、成交量與 ${indicator}。金色點為新聞日">${g}<g id="crosshair" opacity="0"><line id="cross-x" y1="${top}" y2="${base}" stroke="#779393" stroke-dasharray="4 3"/><circle id="cross-dot" r="4.5" fill="#145865" stroke="white" stroke-width="2"/></g><rect id="hit-area" x="${L}" y="0" width="${W-L-R}" height="${H}" fill="transparent"/></svg>`;
 const svg=el.querySelector('svg'),hit=el.querySelector('#hit-area');
 hit.addEventListener('pointermove',ev=>{const bounds=svg.getBoundingClientRect(),vx=(ev.clientX-bounds.left)/bounds.width*W;const i=Math.min(N-1,Math.max(0,Math.floor((vx-L)/step)));const r=rows[i],cross=el.querySelector('#crosshair');cross.setAttribute('opacity','1');const vl=el.querySelector('#cross-x');vl.setAttribute('x1',x(i));vl.setAttribute('x2',x(i));const dot=el.querySelector('#cross-dot');dot.setAttribute('cx',x(i));dot.setAttribute('cy',y(r.close));onHover(r);});
 hit.addEventListener('pointerleave',()=>{el.querySelector('#crosshair').setAttribute('opacity','0');onHover(rows.at(-1));});onHover(rows.at(-1));
}
export function waterfall(dec){
 const W=500,H=200,L=130,R=65,items=[...(dec.factors||[]).map(f=>({name:f.name,v:f.contribution,missing:f.score===null})),{name:'資料不足扣分',v:-dec.missing_deduction},{name:'風險扣分',v:-dec.risk_deduction}];
 const max=Math.max(...items.map(x=>Math.abs(x.v)),8),center=L+(W-L-R)/2,scale=(W-L-R)/2/max;
 return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="各面向相對 50 基準分的實際加減分"><line x1="${center}" x2="${center}" y1="5" y2="${H-15}" stroke="#cad9dc"/>${items.map((r,i)=>{const yy=7+i*23,w=Math.abs(r.v)*scale;return `<text x="0" y="${yy+13}" class="axis">${esc(r.name)}</text><rect x="${r.v<0?center-w:center}" y="${yy+2}" width="${w||1}" height="13" rx="3" fill="${r.missing?'#c6d4d8':r.v>=0?'#218b81':'#bd6470'}"/><text x="${W-2}" y="${yy+13}" class="axis" text-anchor="end">${r.missing?'未取得':(r.v>0?'+':'')+fmt(r.v,1)}</text>`;}).join('')}</svg>`;
}
export function evidenceMap(events){
 const W=450,H=228,L=65,R=28,T=22,B=42,ww=W-L-R,hh=H-T-B;
 const x=v=>L+(v+100)/200*ww,y=v=>T+hh-v*hh;
 let s=`<rect x="${L}" y="${T}" width="${ww}" height="${hh}" fill="#f6faf9" rx="6"/><line x1="${x(0)}" x2="${x(0)}" y1="${T}" y2="${T+hh}" stroke="#afc7c9" stroke-dasharray="4 4"/><text x="${L}" y="${H-13}" class="axis">偏負影響</text><text x="${W-R}" y="${H-13}" text-anchor="end" class="axis">偏正影響</text><text x="8" y="${T+10}" class="axis">文件</text><text x="8" y="${T+hh*.45}" class="axis">摘要</text><text x="8" y="${T+hh}" class="axis">標題</text>`;
 events.filter(e=>e.included).forEach((e,i)=>{const level=e.source_assessment.coverage==='文件節錄'?.9:e.source_assessment.coverage==='摘要可讀'?.5:.12;const offset=(i%3-1)*9;s+=`<circle cx="${x(e.impact_score)+offset}" cy="${y(level)+(i%2)*5}" r="${6+Math.min(7,e.copies?.length||0)}" fill="${e.impact_score<0?'#a86670':e.impact_score>0?'#268e83':'#8c9ca6'}" fill-opacity=".85" stroke="#fff" stroke-width="2"><title>${esc(e.title)} / ${esc(e.impact_label)}</title></circle>`;});
 return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="事件影響與可讀證據層級矩陣；不是統計機率">${s}</svg>`;
}
export function equityChart(rows){
 if(!rows?.length)return '';const W=760,H=170,L=70,R=20,T=15,B=25,min=Math.min(...rows.map(x=>x.value)),max=Math.max(...rows.map(x=>x.value));
 const x=i=>L+i*(W-L-R)/Math.max(1,rows.length-1),y=v=>H-B-(v-min)/(max-min||1)*(H-B-T);let g='';
 for(let i=0;i<3;i++){const v=min+(max-min)*i/2;g+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#dfebec"/><text x="${L-8}" y="${y(v)+3}" text-anchor="end" class="axis">${fmt(v,0)}</text>`;}
 return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="單次模擬的估計資產曲線">${g}<path d="${line(rows,x,y)}" fill="none" stroke="#188b80" stroke-width="2.5"/><text x="${L}" y="${H-3}" class="axis">${rows[0].date}</text><text x="${W-R}" y="${H-3}" class="axis" text-anchor="end">${rows.at(-1).date}</text></svg>`;
}
