const pptxgen = require('pptxgenjs');
const {
  imageSizingCrop,
  imageSizingContain,
  getImageDimensions,
  safeOuterShadow,
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require('/home/oai/skills/slides/pptxgenjs_helpers');
const path = require('path');

const ROOT = __dirname;
const SHOTS = path.join(ROOT, 'assets', 'screenshots');
const OUT = path.join(ROOT, 'StockLab-Free-AI-v14-完整簡報.pptx');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'StockLab / OpenAI';
pptx.subject = '免費台股新聞 AI 分析、每日置頂、Google Sheets 最愛與無洩漏回測';
pptx.title = 'StockLab Free AI v14';
pptx.company = 'StockLab';
pptx.lang = 'zh-TW';
pptx.theme = {
  headFontFace: 'Noto Sans CJK TC',
  bodyFontFace: 'Noto Sans CJK TC',
  lang: 'zh-TW',
};
pptx.defineSlideMaster({
  title: 'MASTER',
  background: { color: '07111F' },
  objects: [
    { rect: { x: 0, y: 0, w: 13.333, h: 0.08, fill: { color: '22D3B6' }, line: { color: '22D3B6' } } },
    { text: { text: 'StockLab Free AI v14', options: { x: 0.48, y: 7.12, w: 4.0, h: 0.18, fontFace: 'Noto Sans CJK TC', fontSize: 8.5, color: '6F829B', margin: 0 } } },
    { text: { text: '研究工具，不構成投資建議', options: { x: 9.35, y: 7.12, w: 3.45, h: 0.18, fontFace: 'Noto Sans CJK TC', fontSize: 8.5, color: '6F829B', align: 'right', margin: 0 } } },
  ],
  slideNumber: { x: 12.87, y: 7.1, color: '6F829B', fontFace: 'Noto Sans CJK TC', fontSize: 8.5 },
});

const C = {
  bg: '07111F', panel: '0D1D31', panel2: '10253C', border: '1E3A56', text: 'F4F8FF', muted: '9FB0C8',
  teal: '22D3B6', cyan: '38BDF8', green: '34D399', orange: 'F59E0B', red: 'FB7185', yellow: 'FACC15', purple: 'A78BFA',
};
const shadow = safeOuterShadow('000000', 0.22, 45, 2.2, 1.0);

function addText(slide, text, x, y, w, h, opts={}) {
  slide.addText(text, {
    x, y, w, h, fontFace: 'Noto Sans CJK TC', fontSize: opts.fontSize || 16,
    color: opts.color || C.text, bold: opts.bold || false, margin: opts.margin ?? 0,
    valign: opts.valign || 'mid', align: opts.align || 'left', breakLine: false,
    fit: 'shrink', paraSpaceAfterPt: opts.paraSpaceAfterPt || 0,
    bullet: opts.bullet, isTextBox: true, ...opts,
  });
}
function title(slide, kicker, heading, sub='') {
  addText(slide, kicker.toUpperCase(), 0.55, 0.38, 3.5, 0.22, { fontSize: 9.5, color: C.teal, bold: true, charSpacing: 1.5 });
  addText(slide, heading, 0.55, 0.67, 12.1, 0.52, { fontSize: 28, bold: true });
  if (sub) addText(slide, sub, 0.57, 1.22, 12.0, 0.38, { fontSize: 12.5, color: C.muted });
}
function card(slide, x, y, w, h, opts={}) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.08,
    fill: { color: opts.fill || C.panel, transparency: opts.transparency || 0 },
    line: { color: opts.line || C.border, width: opts.lineWidth || 1 },
    shadow: opts.shadow === false ? undefined : shadow,
  });
}
function chip(slide, text, x, y, w, color=C.teal) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h: 0.28, rectRadius: 0.08, fill: { color, transparency: 84 }, line: { color, transparency: 58, width: 0.8 } });
  addText(slide, text, x, y+0.005, w, 0.26, { fontSize: 9.5, color, bold: true, align: 'center' });
}
function numberBadge(slide, n, x, y, color=C.orange) {
  slide.addShape(pptx.ShapeType.ellipse, { x, y, w: 0.42, h: 0.42, fill: { color }, line: { color } });
  addText(slide, String(n), x, y+0.005, 0.42, 0.4, { fontSize: 13, color: C.bg, bold: true, align: 'center' });
}
function iconCircle(slide, symbol, x, y, color=C.cyan) {
  slide.addShape(pptx.ShapeType.ellipse, { x, y, w: 0.58, h: 0.58, fill: { color, transparency: 84 }, line: { color, transparency: 55 } });
  addText(slide, symbol, x, y+0.01, 0.58, 0.54, { fontSize: 18, color, bold: true, align: 'center' });
}
function bulletList(slide, items, x, y, w, h, opts={}) {
  const runs=[];
  items.forEach((item, idx)=>{
    runs.push({ text: item, options: { bullet: { indent: 14 }, hanging: 3, breakLine: idx < items.length-1, color: opts.color || C.text, fontSize: opts.fontSize || 14, paraSpaceAfterPt: opts.space || 9 } });
  });
  slide.addText(runs, { x, y, w, h, fontFace:'Noto Sans CJK TC', color:C.text, margin:0.04, breakLine:false, valign:'top', fit:'shrink' });
}
function sectionLabel(slide, text, x, y, color=C.teal) {
  slide.addShape(pptx.ShapeType.rect, { x, y: y+0.05, w:0.055, h:0.25, fill:{color}, line:{color} });
  addText(slide, text, x+0.13, y, 3.8, 0.34, { fontSize: 14, bold:true });
}
function screen(slide, file, x, y, w, h, crop={}) {
  card(slide, x-0.05, y-0.05, w+0.10, h+0.10, { fill:'091827', line:'244760' });
  const img = path.join(SHOTS, file);
  let sizing;
  if (crop.cw !== undefined && crop.ch !== undefined) {
    const dims = getImageDimensions(img);
    sizing = imageSizingCrop(img, x, y, w, h, (crop.cx || 0) / dims.width, (crop.cy || 0) / dims.height, crop.cw / dims.width, crop.ch / dims.height);
  } else {
    sizing = imageSizingCrop(img, x, y, w, h);
  }
  slide.addImage({ path: img, ...sizing });
}
function arrow(slide, x1, y1, x2, y2, color=C.cyan) {
  slide.addShape(pptx.ShapeType.line, { x:x1, y:y1, w:x2-x1, h:y2-y1, line:{ color, width:1.8, beginArrowType:'none', endArrowType:'triangle' } });
}
function metric(slide, value, label, x, y, w, color=C.teal) {
  card(slide, x, y, w, 0.78, { fill:C.panel2, line:C.border, shadow:false });
  addText(slide, value, x+0.14, y+0.08, w-0.28, 0.33, { fontSize:22, bold:true, color });
  addText(slide, label, x+0.14, y+0.43, w-0.28, 0.20, { fontSize:9.5, color:C.muted });
}
function addNotes(slide, text) { if (slide.addNotes) slide.addNotes(text); }

// 1 Cover
{
  const s=pptx.addSlide('MASTER');
  s.background={color:C.bg};
  chip(s,'完全免費 · GitHub-first',0.62,0.62,2.25,C.green);
  addText(s,'StockLab',0.62,1.18,5.6,0.68,{fontSize:42,bold:true});
  addText(s,'Free AI v14',0.62,1.96,5.6,0.48,{fontSize:28,bold:true,color:C.teal});
  addText(s,'每日新聞影響分析 × 最多 Top 5 置頂\n傳統面補全 × Google Sheets 最愛\n無未來洩漏的歷史驗證',0.64,2.66,5.55,1.52,{fontSize:20,bold:true,breakLine:true,valign:'top',paraSpaceAfterPt:9});
  addText(s,'GitHub Pages + Actions｜Hugging Face 開源模型｜Google Apps Script',0.64,4.42,5.75,0.56,{fontSize:13,color:C.muted});
  chip(s,'新聞 -100～+100',0.64,5.18,1.62,C.cyan);
  chip(s,'每日最佳自動置頂',2.38,5.18,1.80,C.orange);
  chip(s,'答案分離回測',4.30,5.18,1.45,C.purple);
  screen(s,'overview.png',6.65,0.72,6.05,5.95,{cx:0,cy:0,cw:1440,ch:1480});
  addText(s,'交付版本：14.0.0-free-ai',0.64,6.38,5.0,0.28,{fontSize:11,color:C.muted});
  addNotes(s,'封面。強調完全免費、每日新聞分析、每日置頂、Google Sheets 最愛與無洩漏回測。');
}

// 2 Problems
{
  const s=pptx.addSlide('MASTER'); title(s,'WHY','原本最需要解決的，不只是「再多一個分數」','真正的問題是資訊過載、證據不透明、歷史驗證容易偷看未來，以及免費部署難以長期維持。');
  const cards=[
    ['01','新聞太多','只有標題與情緒，無法知道影響營收、毛利、估值或風險的哪一段。',C.cyan],
    ['02','分數不透明','健康度或 AI 分數若無來源、權重與完整度，容易造成錯誤信心。',C.orange],
    ['03','傳統面不完整','技術、基本、籌碼、估值與風險散落，缺資料卻常被當作中性。',C.green],
    ['04','回測答案外洩','使用今天的基本面、切點後新聞或未來價格，會讓模型看起來過度準確。',C.red],
    ['05','免費架構不穩','付費 API、常駐後端與多套部署流程，提高維護成本與失敗機率。',C.purple],
  ];
  cards.forEach((d,i)=>{ const x=0.58+(i%3)*4.18; const y=1.85+Math.floor(i/3)*2.18; const w=i<3?3.82:5.85; const xx=i<3?x:0.58+(i-3)*6.12; card(s,xx,y,w,1.78); addText(s,d[0],xx+0.20,y+0.15,0.62,0.32,{fontSize:20,bold:true,color:d[3]}); addText(s,d[1],xx+0.88,y+0.13,w-1.08,0.36,{fontSize:17,bold:true}); addText(s,d[2],xx+0.20,y+0.62,w-0.40,0.88,{fontSize:12.5,color:C.muted,valign:'top'}); });
  addText(s,'設計原則：缺資料要扣分；模型失敗要降級；答案必須與預測分開。',0.65,6.40,12.0,0.38,{fontSize:15,bold:true,color:C.teal,align:'center'});
}

// 3 Solution overview
{
  const s=pptx.addSlide('MASTER'); title(s,'SOLUTION','StockLab v14 的四個核心模組','從「每日資料」一路到「可驗證預測」，每一層都能獨立運作與降級。');
  const cols=[
    ['A','新聞情報層','RSS、GDELT、TWSE 重訊\n關聯性、去重、來源品質\n逐則影響分與機制',C.cyan],
    ['B','綜合研究層','技術、基本、籌碼、估值\n風險與資料完整度\n每日最多 Top 5 置頂',C.green],
    ['C','個人工作區','我的最愛與個人備註\nlocalStorage 優先\nGoogle Sheets 跨裝置',C.orange],
    ['D','驗證與治理','Point-in-time snapshot\n結果檔顯式揭曉\n日期與禁用欄位檢查',C.purple],
  ];
  cols.forEach((d,i)=>{const x=0.55+i*3.17;card(s,x,1.78,2.88,3.76,{fill:i%2?C.panel2:C.panel}); iconCircle(s,d[0],x+0.20,2.02,d[3]); addText(s,d[1],x+0.20,2.78,2.42,0.44,{fontSize:19,bold:true}); addText(s,d[2],x+0.20,3.40,2.48,1.48,{fontSize:13.2,color:C.muted,valign:'top',breakLine:true}); chip(s,i===0?'每日輸入':i===1?'每日排序':i===2?'跨裝置': '先預測後揭曉',x+0.20,5.03,1.55,d[3]);});
  card(s,0.72,5.88,11.88,0.72,{fill:'0A2630',line:'175E65',shadow:false});
  addText(s,'最重要的差異：AI 不是裝飾。每個結論都保留新聞、時間、來源、信心、作用路徑與風險條件。',0.98,6.02,11.36,0.38,{fontSize:15,bold:true,color:C.teal,align:'center'});
}

// 4 Architecture
{
  const s=pptx.addSlide('MASTER'); title(s,'ARCHITECTURE','零常駐伺服器的免費架構','模型在 GitHub runner 本機執行；前端只讀靜態 JSON，最愛則寫入使用者自己的 Google Sheet。');
  const boxes=[
    {x:0.58,y:2.10,w:2.05,h:1.0,t:'免費資料來源',d:'Google News RSS\nGDELT · TWSE',c:C.cyan},
    {x:3.05,y:2.10,w:2.05,h:1.0,t:'GitHub Actions',d:'排程抓取與驗證',c:C.green},
    {x:5.52,y:1.70,w:2.24,h:1.0,t:'財經情緒模型',d:'全量新聞分類',c:C.orange},
    {x:5.52,y:3.00,w:2.24,h:1.0,t:'Qwen3-0.6B',d:'高相關事件解釋',c:C.purple},
    {x:8.20,y:2.10,w:2.05,h:1.0,t:'靜態 JSON',d:'latest · snapshots',c:C.teal},
    {x:10.72,y:2.10,w:2.05,h:1.0,t:'GitHub Pages',d:'純前端研究介面',c:C.cyan},
  ];
  boxes.forEach(b=>{card(s,b.x,b.y,b.w,b.h,{fill:C.panel2,line:b.c,shadow:false}); addText(s,b.t,b.x+0.12,b.y+0.14,b.w-0.24,0.30,{fontSize:15,bold:true,color:b.c,align:'center'}); addText(s,b.d,b.x+0.12,b.y+0.50,b.w-0.24,0.35,{fontSize:10.5,color:C.muted,align:'center',breakLine:true});});
  arrow(s,2.63,2.60,3.05,2.60,C.cyan); arrow(s,5.10,2.60,5.52,2.20,C.green); arrow(s,5.10,2.60,5.52,3.50,C.green); arrow(s,7.76,2.20,8.20,2.52,C.orange); arrow(s,7.76,3.50,8.20,2.68,C.purple); arrow(s,10.25,2.60,10.72,2.60,C.teal);
  card(s,1.30,4.78,4.95,1.08,{fill:C.panel,line:C.orange,shadow:false}); addText(s,'我的最愛',1.52,4.96,1.25,0.28,{fontSize:16,bold:true,color:C.orange}); addText(s,'localStorage 先保存  →  Apps Script  →  Google Sheets',2.78,4.91,3.20,0.42,{fontSize:12.5,color:C.text,align:'center'});
  card(s,7.10,4.78,4.95,1.08,{fill:C.panel,line:C.green,shadow:false}); addText(s,'必要固定費用',7.30,4.92,1.66,0.28,{fontSize:15,bold:true,color:C.green}); addText(s,'NT$ 0',9.04,4.83,1.08,0.48,{fontSize:26,bold:true,color:C.green,align:'center'}); addText(s,'公開 repo / 個人規模 / 服務額度內',10.30,4.94,1.42,0.28,{fontSize:9.5,color:C.muted,align:'center'});
  addText(s,'不依賴 Hugging Face 付費 Serverless Inference；模型權重由 workflow 下載並快取。',0.78,6.28,11.8,0.35,{fontSize:13.5,color:C.muted,align:'center'});
}

// 5 Daily pipeline
{
  const s=pptx.addSlide('MASTER'); title(s,'PIPELINE','每天自動完成的 8 個步驟','工作日台北時間傍晚執行；每一階段都有清楚輸入、輸出與 fallback。');
  const steps=[
    ['1','抓價格與官方資料','Yahoo chart / TWSE OpenAPI / T86'],
    ['2','抓近期新聞','Google News RSS / GDELT / 重訊'],
    ['3','時間截斷','published_at、available_at 不得晚於切點'],
    ['4','關聯與去重','公司別名、代號、標題相似度'],
    ['5','模型分析','情緒分類；有限量 Qwen 結構化解釋'],
    ['6','傳統面計算','SMA、RSI、MACD、ATR、營收、估值、籌碼'],
    ['7','綜合與置頂','通過全部門檻後最多選 Top 5'],
    ['8','鎖定並部署','latest.json、snapshot、GitHub Pages'],
  ];
  steps.forEach((d,i)=>{const row=Math.floor(i/4), col=i%4, x=0.55+col*3.18,y=1.82+row*2.17; card(s,x,y,2.87,1.76,{fill:row?C.panel2:C.panel,shadow:false}); numberBadge(s,d[0],x+0.15,y+0.15,i<4?C.cyan:C.teal); addText(s,d[1],x+0.70,y+0.14,1.95,0.35,{fontSize:15,bold:true}); addText(s,d[2],x+0.17,y+0.66,2.53,0.75,{fontSize:11.5,color:C.muted,valign:'top'}); if(i<7 && col<3) arrow(s,x+2.89,y+0.88,x+3.15,y+0.88,C.border);});
  addText(s,'其中任何一個模型失效，資料仍可用規則備援產生；若全部價格失敗，腳本拒絕覆蓋舊資料。',0.72,6.43,11.9,0.34,{fontSize:13.2,bold:true,color:C.orange,align:'center'});
}

// 6 Models
{
  const s=pptx.addSlide('MASTER'); title(s,'OPEN MODELS','兩層開源模型，加上一層透明規則','不是所有文章都交給生成式模型；將昂貴步驟限制在最高關聯事件。');
  const layers=[
    {y:1.82,c:C.cyan,n:'L1',t:'全量財經情緒',m:'bardsai/finance-sentiment-zh-fast',d:'每則新聞判斷正向 / 中性 / 負向與信心。約 0.1B，適合 CPU 批次。'},
    {y:3.15,c:C.purple,n:'L2',t:'高相關事件解釋',m:'Qwen/Qwen3-0.6B',d:'只整理少量重點新聞，輸出作用機制、期間、類型與風險條件。'},
    {y:4.48,c:C.orange,n:'L3',t:'透明規則備援',m:'transparent-rule-v2',d:'詞彙權重、來源品質、公司關聯、時效衰減；模型失敗也能完成每日更新。'},
  ];
  layers.forEach(l=>{card(s,0.58,l.y,6.02,1.05,{fill:C.panel,line:l.c,shadow:false}); iconCircle(s,l.n,0.78,l.y+0.22,l.c); addText(s,l.t,1.55,l.y+0.13,2.15,0.30,{fontSize:16,bold:true}); addText(s,l.m,3.72,l.y+0.13,2.55,0.30,{fontSize:11.5,color:l.c,bold:true,align:'right'}); addText(s,l.d,1.55,l.y+0.50,4.65,0.36,{fontSize:11.5,color:C.muted});});
  card(s,7.00,1.82,5.70,3.72,{fill:C.panel2,line:C.border});
  chip(s,'結構化事件輸出',7.28,2.08,1.65,C.teal);
  addText(s,'【示範】公司公布營運更新',7.28,2.52,4.90,0.36,{fontSize:17,bold:true});
  metric(s,'+58','影響分',7.28,3.05,1.38,C.green); metric(s,'87%','信心',8.83,3.05,1.38,C.cyan); metric(s,'5-20D','期間',10.38,3.05,1.38,C.orange);
  addText(s,'作用機制',7.30,4.07,1.25,0.26,{fontSize:11,bold:true,color:C.teal});
  addText(s,'若訂單與產品組合改善，可能提高營收能見度與市場對獲利的預期；若需求遞延，正向效果會減弱。',7.30,4.36,4.95,0.65,{fontSize:12.5,color:C.text,valign:'top'});
  chip(s,'市場已提前反映',7.30,5.10,1.72,C.red); chip(s,'需求不如預期',9.17,5.10,1.54,C.red);
  addText(s,'模型只提供結構化閱讀輔助；新聞正向不等於股價必然上漲。',0.72,6.28,12.0,0.36,{fontSize:13.5,bold:true,color:C.yellow,align:'center'});
}

// 7 Scoring
{
  const s=pptx.addSlide('MASTER'); title(s,'SCORING','分數怎麼來：事件證據先加權，再和傳統面整合','所有權重位於設定檔，可追蹤、可修改、可用歷史資料重新校準。');
  card(s,0.58,1.82,6.10,1.15,{fill:'0A2630',line:'175E65',shadow:false});
  addText(s,'事件貢獻 = 影響分 × 信心 × 公司關聯 × 來源品質 × 時效衰減',0.84,2.03,5.58,0.42,{fontSize:16,bold:true,color:C.teal,align:'center'});
  addText(s,'新聞先去重，再做加權平均；不是同一消息轉載越多次，分數就越高。',0.84,2.49,5.58,0.25,{fontSize:10.5,color:C.muted,align:'center'});
  sectionLabel(s,'綜合分預設權重',0.62,3.27);
  const weights=[['新聞',33,C.cyan],['技術',24,C.green],['基本',15,C.orange],['籌碼',10,C.purple],['完整度',8,C.teal]];
  weights.forEach((d,i)=>{const y=3.72+i*0.48; addText(s,d[0],0.80,y,0.68,0.24,{fontSize:11.5,bold:true}); s.addShape(pptx.ShapeType.roundRect,{x:1.58,y:y+0.04,w:4.15,h:0.16,rectRadius:0.04,fill:{color:'17324A'},line:{color:'17324A'}}); s.addShape(pptx.ShapeType.roundRect,{x:1.58,y:y+0.04,w:4.15*d[1]/35,h:0.16,rectRadius:0.04,fill:{color:d[2]},line:{color:d[2]}}); addText(s,`${d[1]}%`,5.85,y,0.62,0.24,{fontSize:11,color:d[2],bold:true,align:'right'});});
  card(s,7.08,1.82,5.62,4.40,{fill:C.panel2,line:C.border});
  addText(s,'置頂不只看總分',7.38,2.10,4.95,0.36,{fontSize:20,bold:true});
  const gates=[['資料完整度','≥ 58%',C.teal],['風險分','≤ 72',C.red],['新聞平均關聯','≥ 0.55',C.cyan],['排序','綜合分 → 新聞分',C.orange]];
  gates.forEach((d,i)=>{const y=2.75+i*0.72; card(s,7.38,y,4.95,0.55,{fill:C.panel,line:d[2],shadow:false}); addText(s,d[0],7.58,y+0.12,2.25,0.26,{fontSize:12.5,bold:true}); addText(s,d[1],9.90,y+0.11,2.13,0.26,{fontSize:13,bold:true,color:d[2],align:'right'});});
  addText(s,'風險採負向折扣 18%；缺資料不會被當成「沒事」。',7.45,5.77,4.75,0.25,{fontSize:11.5,color:C.muted,align:'center'});
}

// 8 Top picks
{
  const s=pptx.addSlide('MASTER'); title(s,'DAILY PICKS','每日最佳自動置頂：先過門檻，再比排序','目的不是發出買進指令，而是把有限研究時間集中到證據最完整的標的。');
  screen(s,'daily.png',0.58,1.72,8.35,4.95,{cx:0,cy:0,cw:1440,ch:1120});
  card(s,9.28,1.72,3.45,4.95,{fill:C.panel2,line:C.border});
  chip(s,'置頂規則',9.55,2.02,1.25,C.orange);
  bulletList(s,[
    '每日最多 5 檔，數量可設定。',
    '顯示入選理由、完整度與主要風險。',
    '高總分但風險過高者不直接置頂。',
    '有新聞時需達公司關聯門檻。',
    '候選不足才用綜合分遞補。',
  ],9.55,2.55,2.85,2.45,{fontSize:12.5,space:11});
  card(s,9.55,5.25,2.85,0.98,{fill:'0A2630',line:'175E65',shadow:false});
  addText(s,'首頁永遠先看 Top 5\n完整排名仍保留',9.72,5.43,2.52,0.52,{fontSize:14,bold:true,color:C.teal,align:'center',breakLine:true});
}

// 9 Traditional
{
  const s=pptx.addSlide('MASTER'); title(s,'TRADITIONAL','傳統面補全：不讓 AI 新聞分數孤立運作','同一頁整合技術、基本、籌碼、估值、風險與資料血緣。');
  screen(s,'traditional.png',4.62,1.72,8.10,5.10,{cx:0,cy:0,cw:1440,ch:1150});
  const modules=[
    ['技術','SMA / EMA / RSI / MACD / KD / ATR / 量比',C.cyan],
    ['基本','月營收、YoY、MoM、本益比、PB、殖利率',C.green],
    ['籌碼','外資、投信、自營商、三大法人合計',C.orange],
    ['風險','波動、超買、估值、負面事件、來源品質',C.red],
    ['資料治理','source、published_at、available_at、fetched_at',C.purple],
  ];
  modules.forEach((d,i)=>{const y=1.85+i*0.94; card(s,0.58,y,3.64,0.72,{fill:C.panel,line:d[2],shadow:false}); addText(s,d[0],0.78,y+0.12,0.68,0.25,{fontSize:14,bold:true,color:d[2]}); addText(s,d[1],1.48,y+0.11,2.48,0.33,{fontSize:10.8,color:C.text});});
  addText(s,'歷史模式找不到真正 archive 時，欄位顯示未取得，不用今天資料倒填。',0.72,6.39,3.36,0.40,{fontSize:11.5,bold:true,color:C.yellow,align:'center'});
}

// 10 Favorites
{
  const s=pptx.addSlide('MASTER'); title(s,'FAVORITES','我的最愛：本機優先，Google Sheets 跨裝置','不需要 Firebase、不需要帳號伺服器；適合個人低敏感度股票書籤與備註。');
  screen(s,'favorites.png',0.58,1.73,5.92,3.50,{cx:0,cy:0,cw:1440,ch:920});
  screen(s,'settings.png',6.82,1.73,5.92,3.50,{cx:0,cy:0,cw:1440,ch:920});
  const flow=[['1','加入 / 移除 / 備註',C.orange],['2','先寫 localStorage',C.cyan],['3','JSONP 同步 Apps Script',C.purple],['4','寫入自己的 Google Sheet',C.green]];
  flow.forEach((d,i)=>{const x=0.78+i*3.12; card(s,x,5.55,2.72,0.76,{fill:C.panel2,line:d[2],shadow:false}); numberBadge(s,d[0],x+0.10,5.72,d[2]); addText(s,d[1],x+0.62,5.68,1.92,0.28,{fontSize:11.8,bold:true,align:'center'}); if(i<3) arrow(s,x+2.73,5.93,x+3.04,5.93,C.border);});
  addText(s,'限制：這不是完整 OAuth 會員系統；同步金鑰只適合低敏感度書籤，不能保存交易或個資。',0.72,6.55,11.90,0.30,{fontSize:11.8,color:C.yellow,align:'center'});
}

// 11 No leak
{
  const s=pptx.addSlide('MASTER'); title(s,'POINT-IN-TIME','歷史驗證：先鎖定預測，之後才揭曉答案','2025-08-15 範例預設不包含該日之後的實際報酬、命中與價格。');
  screen(s,'validation.png',6.35,1.73,6.38,4.68,{cx:0,cy:0,cw:1440,ch:1120});
  card(s,0.58,1.73,5.38,1.62,{fill:C.panel2,line:C.teal});
  iconCircle(s,'🔒',0.82,1.99,C.teal); addText(s,'Snapshot',1.58,1.90,1.75,0.32,{fontSize:20,bold:true,color:C.teal});
  addText(s,'輸入、特徵、分數、預測\navailable_at ≤ 切點',1.58,2.33,3.78,0.58,{fontSize:13,color:C.text,breakLine:true});
  card(s,0.58,3.68,5.38,1.62,{fill:C.panel2,line:C.red});
  iconCircle(s,'!',0.82,3.94,C.red); addText(s,'Result',1.58,3.85,1.75,0.32,{fontSize:20,bold:true,color:C.red});
  addText(s,'actual_return、direction_hit、Brier\n只有明確 --reveal 才另檔產生',1.58,4.28,3.85,0.58,{fontSize:13,color:C.text,breakLine:true});
  arrow(s,3.27,3.35,3.27,3.68,C.orange);
  card(s,0.82,5.69,4.88,0.64,{fill:'2A1E12',line:C.orange,shadow:false});
  addText(s,'Validator 會拒絕未來日期與答案欄位',1.02,5.85,4.48,0.28,{fontSize:13.5,bold:true,color:C.orange,align:'center'});
  addText(s,'回溯建立仍會標示 retrospective；真正前瞻驗證需從現在開始每日保存不可變快照。',0.72,6.51,12.0,0.26,{fontSize:11.8,color:C.muted,align:'center'});
}

// 12 Validation metrics
{
  const s=pptx.addSlide('MASTER'); title(s,'VALIDATION','可信度不是看一個日期有沒有漲','應用 walk-forward、校準、分桶與交易成本後結果，檢查模型在不同市場條件下是否穩定。');
  const ms=[['方向命中率','預測方向 vs. 實際方向',C.cyan],['Brier Score','上漲機率是否校準',C.purple],['1 / 5 / 20 日','不同作用期間的報酬',C.green],['異常報酬','相對 0050 或市場基準',C.orange],['分桶分析','依分數、來源、產業、信心',C.teal],['風險績效','成本後報酬、最大回撤',C.red]];
  ms.forEach((d,i)=>{const x=0.58+(i%3)*4.18,y=1.78+Math.floor(i/3)*1.35;card(s,x,y,3.82,1.08,{fill:C.panel,line:d[2],shadow:false}); addText(s,d[0],x+0.18,y+0.14,1.38,0.30,{fontSize:15,bold:true,color:d[2]}); addText(s,d[1],x+1.60,y+0.14,1.98,0.48,{fontSize:11.2,color:C.muted,align:'right'});});
  card(s,0.58,4.72,5.80,1.48,{fill:C.panel2,line:C.border});
  sectionLabel(s,'Walk-forward',0.82,4.94,C.teal);
  addText(s,'先用較早期間校準 → 凍結規則 → 測試下一段未見資料\n禁止看完整年度答案後再回頭調權重。',0.95,5.34,5.12,0.62,{fontSize:13.2,color:C.text,breakLine:true});
  card(s,6.72,4.72,6.00,1.48,{fill:'291A21',line:C.red});
  sectionLabel(s,'本簡報刻意不揭露 2025-08-15 後答案',6.96,4.94,C.red);
  addText(s,'範例只展示系統如何鎖定當時預測；結果必須由使用者主動 reveal，避免報告本身偷看未來。',7.08,5.34,5.25,0.62,{fontSize:13.2,color:C.text});
}

// 13 Competitor
{
  const s=pptx.addSlide('MASTER'); title(s,'BENCHMARK','參考網站去蕪存菁：保留好用操作，補上證據與驗證','不複製外觀或單一分數，而是把使用者真正需要的快速閱讀流程保留下來。');
  const headers=['參考網站優點','新版保留','StockLab v14 升級'];
  const xs=[0.58,4.58,8.58], ws=[3.65,3.65,4.15];
  headers.forEach((h,i)=>{card(s,xs[i],1.75,ws[i],0.54,{fill:i===2?'0A2630':C.panel2,line:i===2?C.teal:C.border,shadow:false}); addText(s,h,xs[i]+0.12,1.85,ws[i]-0.24,0.26,{fontSize:14,bold:true,color:i===2?C.teal:C.text,align:'center'});});
  const rows=[
    ['快速健康度','保留總覽與排名','拆成 6 個分項 + 風險 + 完整度'],
    ['條件篩選','保留 AND 條件與預設','加入新聞分、外資、量比、風險門檻'],
    ['技術與籌碼','保留指標卡與支撐壓力','加入資料血緣與 point-in-time'],
    ['收藏功能','保留快速收藏','localStorage + Google Sheets 跨裝置'],
    ['歷史/排名','保留歷史切換','snapshot / result 分離與 validator'],
    ['AI 綜合分','保留一頁式閱讀','逐則新聞證據、信心、機制與失效條件'],
  ];
  rows.forEach((r,ri)=>{const y=2.43+ri*0.66; r.forEach((t,i)=>{card(s,xs[i],y,ws[i],0.54,{fill:ri%2?C.panel:'0A1828',line:C.border,shadow:false}); addText(s,t,xs[i]+0.12,y+0.08,ws[i]-0.24,0.36,{fontSize:11.2,color:i===2?C.text:C.muted,bold:i===2});});});
  addText(s,'差異化重點：新聞不是旁邊多一個情緒標籤，而是整個排序與驗證系統的可追蹤證據。',0.75,6.58,11.8,0.30,{fontSize:13.5,bold:true,color:C.teal,align:'center'});
}

// 14 Deployment
{
  const s=pptx.addSlide('MASTER'); title(s,'DEPLOY','部署到 GitHub：不需要 Node build，也不需要伺服器','將 ZIP 內容放到 Repository 根目錄，啟用 Actions 與 Pages 即可。');
  const steps=[
    ['1','建立 Public Repository','新 repo 最安全；既有 stocklab 先建備份分支。'],
    ['2','上傳整包檔案','確認 .github/workflows 隱藏資料夾也已提交。'],
    ['3','Pages 選 GitHub Actions','pages.yml 直接部署 Repository 根目錄。'],
    ['4','允許 workflow 寫入','daily-update.yml 需要提交新的 data JSON。'],
    ['5','手動跑第一次每日更新','模型下載、資料抓取、測試、commit、Pages 重部署。'],
  ];
  steps.forEach((d,i)=>{const y=1.75+i*0.91; numberBadge(s,d[0],0.68,y+0.08,i<2?C.cyan:i<4?C.teal:C.orange); card(s,1.30,y,6.22,0.70,{fill:i%2?C.panel2:C.panel,line:C.border,shadow:false}); addText(s,d[1],1.52,y+0.10,2.18,0.27,{fontSize:14.5,bold:true}); addText(s,d[2],3.74,y+0.10,3.48,0.35,{fontSize:11.3,color:C.muted,align:'right'});});
  card(s,8.02,1.75,4.70,4.72,{fill:C.panel2,line:C.border});
  chip(s,'內建 workflows',8.34,2.04,1.58,C.green);
  const wf=[['daily-update.yml','每日抓取、模型、置頂、commit'],['pages.yml','push / 資料 workflow 完成後部署'],['historical-backfill.yml','指定日期 snapshot / 可選 reveal'],['quality.yml','JSON、JS、pytest、no-leak']];
  wf.forEach((d,i)=>{const y=2.58+i*0.76; card(s,8.32,y,4.08,0.58,{fill:C.panel,line:i===0?C.green:C.border,shadow:false}); addText(s,d[0],8.48,y+0.08,1.52,0.22,{fontSize:10.5,bold:true,color:i===0?C.green:C.cyan}); addText(s,d[1],10.05,y+0.08,2.17,0.28,{fontSize:9.6,color:C.muted,align:'right'});});
  addText(s,'排程直接指定 Asia/Taipei 工作日 18:20；GitHub 仍可能延遲，長期無活動也需留意停用。',8.34,5.86,4.05,0.42,{fontSize:10.8,color:C.yellow,align:'center'});
}

// 15 Free operations
{
  const s=pptx.addSlide('MASTER'); title(s,'FREE OPERATIONS','免費不等於沒有邊界：用降級策略把風險變成可管理','核心原則是「任何付費服務都不是必要依賴」。');
  const items=[
    ['網站','GitHub Pages','NT$0','公開 repo；依平台條款',C.cyan],
    ['排程','GitHub Actions','NT$0','公開 repo / 額度與政策內',C.green],
    ['模型','HF 權重本機推論','NT$0','首次下載較久；CPU 速度有限',C.purple],
    ['資料','RSS / GDELT / TWSE','NT$0','端點可能延遲、限流或改版',C.orange],
    ['最愛','Apps Script + Sheets','NT$0','個人配額；非正式會員系統',C.teal],
    ['回填','Kaggle Notebook 選用','NT$0','免費 GPU 額度與執行限制',C.red],
  ];
  const colXs=[0.58,3.02,6.00,8.10,10.42], colWs=[2.28,2.78,1.86,2.15,2.32];
  ['元件','免費方案','固定費用','適用範圍','主要限制'].forEach((h,i)=>{card(s,colXs[i],1.75,colWs[i],0.50,{fill:'0A2630',line:C.teal,shadow:false}); addText(s,h,colXs[i]+0.08,1.85,colWs[i]-0.16,0.24,{fontSize:12.2,bold:true,color:C.teal,align:'center'});});
  items.forEach((r,ri)=>{const y=2.37+ri*0.58; const vals=[r[0],r[1],r[2],r[3].split('；')[0],r[3].split('；')[1]||r[3]]; vals.forEach((v,i)=>{card(s,colXs[i],y,colWs[i],0.48,{fill:ri%2?C.panel2:C.panel,line:C.border,shadow:false}); addText(s,v,colXs[i]+0.08,y+0.07,colWs[i]-0.16,0.30,{fontSize:i===2?12.5:9.9,bold:i===2,color:i===2?r[4]:(i===0?C.text:C.muted),align:i===2?'center':'left'});});});
  card(s,0.72,6.20,11.90,0.58,{fill:'2A1E12',line:C.orange,shadow:false});
  addText(s,'Qwen 太慢 → skip_qwen；情緒模型失敗 → 規則；Apps Script 失效 → localStorage；全部價格失敗 → 不覆蓋舊資料。',0.94,6.34,11.45,0.28,{fontSize:11.8,bold:true,color:C.orange,align:'center'});
}

// 16 Project handoff
{
  const s=pptx.addSlide('MASTER'); title(s,'HANDOFF','交付不是單一網頁，而是一套可維護專案','程式、設定、資料、模型策略、Apps Script、工作流程、測試與說明全部放在同一包。');
  card(s,0.58,1.75,6.10,4.82,{fill:'081827',line:C.border});
  addText(s,`stocklab-free-ai-v14/\n├─ index.html + assets/\n├─ config/stocks.json + settings.json\n├─ data/latest.json\n├─ data/snapshots/ + results/\n├─ scripts/\n│  ├─ news_sources.py / market_sources.py\n│  ├─ ai_analysis.py / scoring.py\n│  ├─ update_daily.py / backtest.py\n│  └─ validate_no_leak.py / quality_check.py\n├─ google-apps-script/\n├─ notebooks/StockLab_Backfill_Kaggle.ipynb\n├─ tests/\n└─ .github/workflows/`,0.90,2.02,5.48,4.15,{fontFace:'Noto Sans Mono CJK TC',fontSize:12.1,color:'C9D8E9',valign:'top',breakLine:true});
  metric(s,'7 / 7','離線測試通過',7.10,1.85,2.35,C.green); metric(s,'2','無答案 snapshots',9.65,1.85,2.35,C.teal);
  card(s,7.10,2.95,4.90,1.06,{fill:C.panel2,line:C.green}); addText(s,'✓ JSON 格式\n✓ JavaScript 語法\n✓ 技術指標與分數\n✓ 置頂門檻\n✓ No-leak 禁用欄位',7.38,3.12,4.35,0.68,{fontSize:12.3,color:C.text,breakLine:true});
  card(s,7.10,4.30,4.90,1.28,{fill:C.panel2,line:C.orange}); addText(s,'正式上線後的第一件事',7.38,4.50,4.35,0.28,{fontSize:15,bold:true,color:C.orange}); addText(s,'手動執行 Daily free news analysis，讓真實資料取代清楚標示的合成 demo。',7.38,4.87,4.35,0.48,{fontSize:12.2,color:C.muted});
  card(s,7.10,5.88,4.90,0.60,{fill:'0A2630',line:C.teal,shadow:false}); addText(s,'ZIP 解壓 → 上傳 GitHub → 啟用 Pages → Run workflow',7.30,6.03,4.50,0.28,{fontSize:12.4,bold:true,color:C.teal,align:'center'});
}

// 17 Roadmap
{
  const s=pptx.addSlide('MASTER'); title(s,'ROADMAP','從可用版本走向可信研究系統','先累積每日不可變快照，再用 walk-forward 決定哪些模型與權重真的值得保留。');
  const phases=[
    ['現在','上線與穩定','部署 Pages、設定 Sheets、每日保存 snapshot、監控來源失敗。',C.green],
    ['1-2 個月','累積驗證樣本','分數分桶、Brier、1/5/20 日、產業與來源分析。',C.cyan],
    ['3-6 個月','校準與資料擴充','歷史基本面 archive、benchmark 異常報酬、事件群聚去重。',C.orange],
    ['之後','多人與進階模型','需要時才升級 Auth、資料庫、更大模型與正式後端。',C.purple],
  ];
  phases.forEach((d,i)=>{const x=0.58+i*3.17; card(s,x,1.86,2.88,3.58,{fill:i%2?C.panel2:C.panel,line:d[3]}); chip(s,d[0],x+0.22,2.12,1.12,d[3]); addText(s,d[1],x+0.22,2.69,2.42,0.60,{fontSize:19,bold:true,color:d[3]}); addText(s,d[2],x+0.22,3.52,2.42,1.16,{fontSize:12.7,color:C.muted,valign:'top'});});
  card(s,1.08,5.88,11.15,0.70,{fill:'0A2630',line:C.teal,shadow:false});
  addText(s,'先建立可信的資料時間線，再追求更大的模型；否則更聰明的模型只會更有說服力地偷看未來。',1.34,6.06,10.65,0.32,{fontSize:15,bold:true,color:C.teal,align:'center'});
}

// 18 References
{
  const s=pptx.addSlide('MASTER'); title(s,'REFERENCES','主要官方文件與模型來源','部署前仍應再次確認各服務最新條款、額度、端點與 model card。');
  const refs=[
    ['GitHub Pages / Actions','docs.github.com/pages/getting-started-with-github-pages\ndocs.github.com/actions/using-workflows/events-that-trigger-workflows#schedule'],
    ['Google Apps Script','developers.google.com/apps-script/guides/web\ndevelopers.google.com/apps-script/guides/services/quotas'],
    ['Hugging Face 模型','huggingface.co/bardsai/finance-sentiment-zh-fast\nhuggingface.co/Qwen/Qwen3-0.6B'],
    ['TWSE OpenAPI','openapi.twse.com.tw\nwww.twse.com.tw/rwd/zh/fund/T86'],
    ['參考網站','kmuftp-creater.github.io/tw-stock-analyzer/'],
    ['原始作品','github.com/flyree140/stocklab'],
  ];
  refs.forEach((d,i)=>{const x=0.58+(i%2)*6.20,y=1.78+Math.floor(i/2)*1.42;card(s,x,y,5.85,1.14,{fill:i%2?C.panel2:C.panel,line:C.border,shadow:false}); addText(s,d[0],x+0.22,y+0.15,1.55,0.30,{fontSize:14.5,bold:true,color:i<2?C.teal:i<4?C.cyan:C.orange}); addText(s,d[1],x+1.80,y+0.15,3.78,0.64,{fontSize:10.6,color:C.muted,breakLine:true});});
  addText(s,'StockLab Free AI v14｜完整專案、ZIP 與簡報均已重新生成',0.72,6.43,11.9,0.36,{fontSize:17,bold:true,color:C.text,align:'center'});
}

for (const slide of pptx._slides) {
  try { warnIfSlideHasOverlaps(slide, pptx); warnIfSlideElementsOutOfBounds(slide, pptx); } catch (e) {}
}

pptx.writeFile({ fileName: OUT }).then(() => console.log(`Wrote ${OUT}`));
