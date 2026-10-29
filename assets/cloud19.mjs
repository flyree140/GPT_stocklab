/** Private Google Sheets journal. OAuth drive.file only; token is memory-only.
 * Append-only IDs + hash checks make retries idempotent. Concurrent conflicting
 * trades are DETECTED after merge, not silently discarded or declared atomic.
 */
export const SCOPE19='https://www.googleapis.com/auth/drive.file';
export const HEADERS19=['ID','類型','儲存時間','裝置ID','不可手改的JSON','SHA256'];
export const SHEETS19=['說明','同步紀錄','成交流水','保存計畫','我的設定','持股摘要','成果摘要'];
const enc=encodeURIComponent;
export function canonical19(x){
 if(x===null)return 'null';
 if(typeof x==='number'){if(!Number.isFinite(x))throw Error('雲端內容含無效數字');return JSON.stringify(x)}
 if(typeof x==='string'||typeof x==='boolean')return JSON.stringify(x);
 if(Array.isArray(x))return '['+x.map(canonical19).join(',')+']';
 if(typeof x==='object')return '{'+Object.keys(x).filter(k=>x[k]!==undefined).sort().map(k=>JSON.stringify(k)+':'+canonical19(x[k])).join(',')+'}';
 throw Error('不支援的雲端資料類型');
}
export async function hash19(x){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical19(x))))].map(v=>v.toString(16).padStart(2,'0')).join('')}
export async function record19(kind,payload,id,device,createdAt=new Date().toISOString()){
 if(!['event','plan','settings'].includes(kind)||typeof id!=='string'||!id)throw Error('雲端紀錄格式不正確');
 const r={id,kind,createdAt,device,payload};const sha=await hash19(r);return {...r,sha};
}
export function recordRow19(r){const body=canonical19(r.payload);if(body.length>40000)throw Error('單筆內容超過個人版限制；原本機紀錄保留');return [r.id,r.kind,r.createdAt,r.device,body,r.sha]}
export async function parseRows19(rows){const out=[];for(const row of rows){if(!row[0])continue;if(row.length<6)throw Error('活頁簿有不完整紀錄，停止覆寫');let payload;try{payload=JSON.parse(row[4])}catch{throw Error('活頁簿同步內容不是有效JSON')}
 const r={id:row[0],kind:row[1],createdAt:row[2],device:row[3],payload};if(!['event','plan','settings'].includes(r.kind)||!Number.isFinite(Date.parse(r.createdAt))||typeof r.device!=='string')throw Error('雲端紀錄欄位無效');if(await hash19(r)!==row[5])throw Error('活頁簿內容雜湊不符：可能被手動修改；停止合併');out.push({...r,sha:row[5]});}
 return dedupe19(out);
}
export function dedupe19(records){const by=new Map;for(const r of records){const k=r.kind+':'+r.id;const old=by.get(k);if(old&&old.sha!==r.sha)throw Error('相同ID有不同內容，需人工核對，不會覆蓋');if(!old)by.set(k,r)}return [...by.values()]}
export function settingsHeads19(records){const rows=records.filter(r=>r.kind==='settings');const referenced=new Set(rows.flatMap(r=>r.payload.parents||[]));return rows.filter(r=>!referenced.has(r.id))}
export function materialize19(records,local,validator,preferSettings=null){
 records=dedupe19(records);const result={account:{...local.account,events:[],plans:[]},profile:local.profile,favorites:local.favorites};
 for(const r of records){if(r.kind==='event'){if(r.payload.id!==r.id)throw Error('成交ID不一致');result.account.events.push(r.payload)}if(r.kind==='plan'){if(r.payload.id!==r.id)throw Error('計畫ID不一致');result.account.plans.push(r.payload)}}
 const heads=settingsHeads19(records);
 if(heads.length>1&&!preferSettings)throw Error('設定有多裝置衝突：先選「以這台設定解決」；帳本紀錄不會刪除');
 if(preferSettings){result.profile=preferSettings.profile;result.favorites=preferSettings.favorites}
 else if(heads.length===1){result.profile=heads[0].payload.profile;result.favorites=heads[0].payload.favorites}
 result.account.events.sort((a,b)=>a.date.localeCompare(b.date)||a.recordedAt.localeCompare(b.recordedAt)||a.id.localeCompare(b.id));
 validator(result);return result;
}
export class SheetsJournal19{
 constructor({clientId='',fetcher=globalThis.fetch,onStatus=()=>{}}={}){this.clientId=clientId;this.fetcher=fetcher;this.onStatus=onStatus;this.token=null;this.expires=0;this.sheet=null;this.busy=false;this._gis=null;this.calls=[];this.dayCalls=0;this.rateWaitMs=2500;this.lastCall=0;}
 async loadIdentity(){
  if(globalThis.google?.accounts?.oauth2)return;
  if(this._gis)return this._gis;
  this._gis=new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='https://accounts.google.com/gsi/client';s.async=true;s.onload=()=>resolve();s.onerror=()=>{this._gis=null;reject(Error('Google登入元件無法載入；本機帳本已保留'))};document.head.appendChild(s)});return this._gis;
 }
 async connect(){
  if(!/^[0-9]+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com$/.test(this.clientId))throw Error('先完成網站管理者一次性的Google OAuth Client ID設定');
  // Identity library must be loaded before this click to preserve popup gesture.
  if(!globalThis.google?.accounts?.oauth2){await this.loadIdentity();throw Error('Google登入元件已準備；請再按一次「登入Google」')}
  return new Promise((resolve,reject)=>{const c=google.accounts.oauth2.initTokenClient({client_id:this.clientId,scope:SCOPE19,callback:r=>{if(r.error){reject(Error('Google授權失敗：'+r.error));return}if(!google.accounts.oauth2.hasGrantedAllScopes(r,SCOPE19)){reject(Error('需要本應用建立的檔案權限，未要求整個雲端硬碟'));return}this.token=r.access_token;this.expires=Date.now()+(Number(r.expires_in)||3600)*1000;this.onStatus('connected');resolve()},error_callback:e=>reject(Error('Google登入未完成：'+e.type))});c.requestAccessToken({prompt:'select_account'})});
 }
 disconnect(){this.token=null;this.expires=0;this.sheet=null;this.onStatus('disconnected')}
 async revoke(){const t=this.token;this.disconnect();if(t&&globalThis.google?.accounts?.oauth2)await new Promise(resolve=>google.accounts.oauth2.revoke(t,resolve))}
 async api(url,method='GET',body=null){
  if(!this.token||Date.now()>=this.expires-30000)throw Error('Google登入已過期，請重新登入；未同步紀錄仍在本機');
  if(!/^https:\/\/(sheets\.googleapis\.com|www\.googleapis\.com)\//.test(url))throw Error('不允許的Google API位置');
  if(++this.dayCalls>1000)throw Error('本頁Google API已達1000次保護上限，停止自動請求；請核對配額');
  const wait=Math.max(0,this.rateWaitMs-(Date.now()-this.lastCall));if(wait)await new Promise(r=>setTimeout(r,wait));this.lastCall=Date.now();
  const r=await this.fetcher(url,{method,headers:{Authorization:'Bearer '+this.token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  if(!r.ok){if(r.status===401){this.token=null;this.onStatus('expired')}throw Error(`Google服務回傳 ${r.status}；未確認雲端成功，請稍後登入重試`)}
  return r.status===204?{}:r.json();
 }
 async discover(){const q="trashed = false and mimeType = 'application/vnd.google-apps.spreadsheet' and appProperties has { key='stocklabJournal' and value='19' }";let files=[],page='';do{const r=await this.api('https://www.googleapis.com/drive/v3/files?q='+enc(q)+'&fields=nextPageToken,files(id,name,webViewLink)&pageSize=100'+(page?'&pageToken='+enc(page):''));files.push(...(r.files||[]));page=r.nextPageToken||'';}while(page);return files;}
 async create(){
  const sheets=SHEETS19.map((title,i)=>({properties:{sheetId:i,title,gridProperties:{rowCount:1000,columnCount:14,frozenRowCount:1}}}));
  const s=await this.api('https://sheets.googleapis.com/v4/spreadsheets','POST',{properties:{title:'StockLab 私人投資帳本',locale:'zh_TW',timeZone:'Asia/Taipei'},sheets});
  this.sheet=s.spreadsheetId;
  // No permissions.create call: the workbook remains private to the Google user.
  await this.api('https://www.googleapis.com/drive/v3/files/'+this.sheet,'PATCH',{appProperties:{stocklabJournal:'19'}});
  const heads=[['說明',['StockLab私人投資帳本','此檔不公開到GitHub；不是券商帳戶']],['同步紀錄',['ID','類型','儲存時間','裝置ID','不可手改的JSON','SHA256']],['成交流水',['紀錄ID','日期','種類','股票','名稱','股數','均價','手續費','證交稅','資金金額','計畫ID','備註','更正目標']],['保存計畫',['計畫ID','保存時間','股票','有效日','限價','股數','停損','目標情境','最多交易日','來源雜湊']],['我的設定',['項目','值']],['持股摘要',['股票','名稱','股數','帳面成本','市值','未實現損益','行情日期']],['成果摘要',['指標','值','說明']]];
  await this.values(heads.map(([n,h])=>({range:`'${n}'!A1`,values:[h]})));
  await this.values([{range:"'說明'!A2",values:[['使用方式','只從網站記錄成交。同步紀錄是追加式主資料，請勿手改。'],['隱私','不要設成任何知道連結的人；網站不要求券商密碼。'],['同步限制','單人跨裝置；同時互相衝突的成交會阻擋，並非交易級資料庫。'],['回復','Google登入過期需點擊重登；未同步不冒充雲端已存。'],['價值','成果摘要由網站按記錄重新計算；不保證投資獲利。']]}]);
  await this.api(`https://sheets.googleapis.com/v4/spreadsheets/${this.sheet}:batchUpdate`,'POST',{requests:SHEETS19.flatMap((_,sheetId)=>[{repeatCell:{range:{sheetId,startRowIndex:0,endRowIndex:1},cell:{userEnteredFormat:{backgroundColor:{red:.06,green:.19,blue:.23},textFormat:{bold:true,foregroundColor:{red:1,green:1,blue:1}},wrapStrategy:'WRAP'}},fields:'userEnteredFormat'}},{updateDimensionProperties:{range:{sheetId,dimension:'COLUMNS',startIndex:0,endIndex:14},properties:{pixelSize:160},fields:'pixelSize'}}])});
  return {id:this.sheet,name:'StockLab 私人投資帳本',webViewLink:`https://docs.google.com/spreadsheets/d/${this.sheet}/edit`};
 }
 async select(id){if(!/^[A-Za-z0-9_-]+$/.test(id))throw Error('活頁簿ID格式不正確');const s=await this.api(`https://sheets.googleapis.com/v4/spreadsheets/${id}?fields=spreadsheetId,sheets.properties.title`);const titles=s.sheets.map(x=>x.properties.title);if(!SHEETS19.every(t=>titles.includes(t)))throw Error('不是StockLab19活頁簿，禁止覆蓋其他試算表');this.sheet=id;return s;}
 async values(data){if(!this.sheet)throw Error('請選擇私人活頁簿');return this.api(`https://sheets.googleapis.com/v4/spreadsheets/${this.sheet}/values:batchUpdate`,'POST',{valueInputOption:'RAW',data});}
 async read(){if(!this.sheet)throw Error('請先建立或選擇投資活頁簿');const r=await this.api(`https://sheets.googleapis.com/v4/spreadsheets/${this.sheet}/values/${enc("'同步紀錄'!A:F")}`);const rows=r.values||[];if(!rows.length||HEADERS19.some((h,i)=>rows[0][i]!==h))throw Error('活頁簿主表標頭不符或建立未完成；停止寫入，原資料不動');if(rows.length>20001)throw Error('超過個人版20000筆上限，請先備份，不截斷帳本');return parseRows19(rows.slice(1))}
 async sync(localRecords,validator,local){
  if(this.busy)throw Error('正在同步，請勿重複點擊');this.busy=true;this.onStatus('syncing');
  try{
   const remote=await this.read(),union=dedupe19([...remote,...localRecords]);materialize19(union,local,validator);
   const keys=new Set(remote.map(r=>r.kind+':'+r.id));const fresh=localRecords.filter(r=>!keys.has(r.kind+':'+r.id));
   for(let i=0;i<fresh.length;){let values=[],bytes=0;while(i<fresh.length&&values.length<100){const row=recordRow19(fresh[i]),size=new TextEncoder().encode(JSON.stringify(row)).length;if(values.length&&bytes+size>800000)break;values.push(row);bytes+=size;i++;}await this.api(`https://sheets.googleapis.com/v4/spreadsheets/${this.sheet}/values/${enc("'同步紀錄'!A:F")}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`,'POST',{range:"'同步紀錄'!A:F",majorDimension:'ROWS',values});}
   const confirmed=await this.read(),index=new Map(confirmed.map(r=>[r.kind+':'+r.id,r.sha]));
   if(localRecords.some(r=>index.get(r.kind+':'+r.id)!==r.sha))throw Error('雲端未完整確認，不標示已同步，請重試');
   const merged=materialize19(confirmed,local,validator); // detects concurrent overspend / profile forks
   this.onStatus('synced');return {records:confirmed,bundle:merged,at:new Date().toISOString()};
  }catch(e){this.onStatus('error',e.message);throw e}finally{this.busy=false}
 }
 async projections(bundle,balance){
  const eventRows=bundle.account.events.map(e=>[e.id,e.date,e.type,e.symbol||'',e.name||'',e.quantity??'',e.price??'',e.fee??'',e.tax??'',e.amount??'',e.planId||'',e.note||'',e.target||'']);
  const planRows=bundle.account.plans.map(p=>[p.id,p.savedAt,p.ticket?.symbol||'',p.ticket?.expiry||'',p.ticket?.entry??'',p.ticket?.conditionalShares??'',p.ticket?.stop??'',p.ticket?.target??'',p.ticket?.holdDays??'',p.source?.snapshot||'']);
  const holdingRows=(balance.holdings||[]).map(h=>[h.symbol,h.name,h.quantity,h.cost,h.quoteMissing?null:h.marketValue,h.quoteMissing?null:h.unrealizedPnl,h.quoteDate]);
  const data=[['成交流水',eventRows],['保存計畫',planRows],['我的設定',Object.entries(bundle.profile).map(([k,v])=>[k,v])],['持股摘要',holdingRows],['成果摘要', [['更新時間',new Date().toISOString(),'由實際填報成交計算，非券商回報'],['累計投入',balance.contributions,'投入不是獲利'],['已提款',balance.withdrawals,''],['可用現金',balance.spendableCash,'不含待交割款'],['待交割',balance.unsettled,''],['已實現損益',balance.realizedPnl,''],['未實現損益',balance.allPriced?balance.unrealizedPnl:'待有效行情',balance.allPriced?'依來源收盤估值，非即時':'缺適用行情，不把按成本記值當成零風險'],['累計股息',balance.dividends,'實際收到才記錄']]]];
  // These sheets are human-readable projections, not journal authority.
  await this.api(`https://sheets.googleapis.com/v4/spreadsheets/${this.sheet}/values:batchClear`,'POST',{ranges:data.map(([n])=>`'${n}'!A2:N`)});
  await this.values(data.filter(([,rows])=>rows.length).map(([n,rows])=>({range:`'${n}'!A2`,values:rows.map(r=>r.map(v=>v===undefined||v===null?'':v))})));
 }
}
