/** StockLab 16: personal watchlist with optimistic concurrency and tombstones.
 * Script properties: STOCKLAB_TOKEN, STOCKLAB_READ_TOKEN (separate, >=20 chars),
 * ALLOWED_ORIGIN=https://flyree140.github.io ; SPREADSHEET_ID optional if bound.
 * Deploy: execute as owner; anyone. POST key required. Do not expose finance secrets.
 */
var HEADERS16=['client','symbol','name','note','active','revision'];
function doGet(){return ContentService.createTextOutput(JSON.stringify({service:'StockLab 16 watchlist',version:16,authentication:'POST token required'})).setMimeType(ContentService.MimeType.JSON);}
function doPost(e){
 var p=(e&&e.parameter)||{},payload;
 try{payload=handle16_(p);}catch(err){payload={ok:false,error:String(err.message||err)};}
 if(p.response_type==='bridge')return bridge16_(payload,p);
 return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}
function handle16_(p){
 var props=PropertiesService.getScriptProperties(),action=String(p.action||'');
 var expected=props.getProperty(action==='feed'?'STOCKLAB_READ_TOKEN':'STOCKLAB_TOKEN');
 if(!expected||expected.length<20||!constantEqual16_(String(p.token||''),expected))throw Error('未授權：請檢查伺服器金鑰與部署版本');
 if(action==='ping')return {ok:true,version:16};
 var lock=LockService.getScriptLock();lock.waitLock(10000);
 try{
  var sheet=sheet16_(),rows=rows16_(sheet),client=String(p.client||'personal').slice(0,64);
  if(action==='feed')return {ok:true,symbols:Array.from(new Set(rows.filter(function(r){return r.active;}).map(function(r){return r.symbol;}))).slice(0,30)};
  if(action!=='sync')throw Error('不支援的動作');
  if(p.response_type==='bridge'&&String(p.site_origin)!==props.getProperty('ALLOWED_ORIGIN'))throw Error('請在 Script properties 設定正確的 ALLOWED_ORIGIN');
  var edits=JSON.parse(p.mutations||'[]');if(!Array.isArray(edits)||edits.length>100)throw Error('每次最多同步 100 筆');
  var accepted=[],conflicts=[];
  edits.forEach(function(m){
   var symbol=String(m.symbol||'');if(!/^\d{4,6}[AB]?\.(TW|TWO)$/.test(symbol))throw Error('股票代號格式不正確');
   var old=rows.find(function(r){return r.client===client&&r.symbol===symbol;}),base=Number(m.base_revision||0);
   if((old&&old.revision!==base)||(!old&&base!==0)){conflicts.push(old||{symbol:symbol,name:symbol,note:'',active:false,revision:0});return;}
   if(!old&&rows.length>=500)throw Error('個人版最多 500 筆（含刪除紀錄）；請先備份整理');
   var next={client:client,symbol:symbol,name:String(m.name||symbol).slice(0,80),note:String(m.note||'').slice(0,500),active:m.active===true||m.active==='true',revision:(old?old.revision:0)+1};
   if(old){var idx=rows.indexOf(old);rows[idx]=next;}else rows.push(next);
   accepted.push(symbol);
  });
  if(edits.length){
   var values=rows.map(function(r){return HEADERS16.map(function(h){return typeof r[h]==='string'?safeCell16_(r[h]):r[h];});});
   if(values.length)sheet.getRange(2,1,values.length,HEADERS16.length).setValues(values);
  }
  // Always return tombstones; otherwise an offline device can resurrect deletions.
  return {ok:true,version:16,rows:rows.filter(function(r){return r.client===client;}),accepted:accepted,conflicts:conflicts};
 }finally{lock.releaseLock();}
}
function constantEqual16_(a,b){var n=Math.max(a.length,b.length),x=a.length^b.length;for(var i=0;i<n;i++)x|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);return x===0;}
function safeCell16_(text){return /^[=+@\-\t\r]/.test(text)?"'"+text:text;}
function sheet16_(){
 var props=PropertiesService.getScriptProperties(),id=props.getProperty('SPREADSHEET_ID');
 var ss=id?SpreadsheetApp.openById(id):SpreadsheetApp.getActiveSpreadsheet();if(!ss)throw Error('找不到 Spreadsheet；請設定 SPREADSHEET_ID');
 var sheet=ss.getSheetByName('Favorites16');if(!sheet)sheet=ss.insertSheet('Favorites16');
 if(!sheet.getLastRow()){sheet.appendRow(HEADERS16);sheet.setFrozenRows(1);}
 return sheet;
}
function rows16_(sheet){
 if(sheet.getLastRow()<2)return [];
 return sheet.getRange(2,1,sheet.getLastRow()-1,HEADERS16.length).getValues().filter(function(v){return v[1];}).map(function(v){
  return {client:String(v[0]),symbol:String(v[1]),name:String(v[2]),note:String(v[3]),active:v[4]===true||String(v[4])==='true',revision:Number(v[5])||0};
 });
}
function bridge16_(payload,p){
 var allowed=PropertiesService.getScriptProperties().getProperty('ALLOWED_ORIGIN')||'';
 if(!/^https:\/\/[a-zA-Z0-9.-]+(?::\d+)?$/.test(allowed))return HtmlService.createHtmlOutput('ALLOWED_ORIGIN not configured');
 var msg={type:'stocklab16-response',nonce:String(p.nonce||'').slice(0,80),payload:payload};
 var encoded=Utilities.base64Encode(JSON.stringify(msg),Utilities.Charset.UTF_8);
 // Base64 prevents injected </script>, and no key is reflected to the browser.
 var html='<html><body><script>var bytes=Uint8Array.from(atob("'+encoded+'"),function(c){return c.charCodeAt(0);});var m=JSON.parse(new TextDecoder().decode(bytes));window.top.postMessage(m,'+JSON.stringify(allowed)+');</script></body></html>';
 return HtmlService.createHtmlOutput(html).setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
/** Optional one-time importer. Copies old Favorites rows; never deletes old sheet.
 * Run manually after checking the old sheet headers. Imported into group personal.
 */
function importOldFavorites(){
 var ss=SpreadsheetApp.getActiveSpreadsheet(),old=ss.getSheetByName('Favorites');if(!old||old.getLastRow()<2)throw Error('找不到舊 Favorites 工作表');
 var grid=old.getDataRange().getValues(),heads=grid.shift().map(String),lock=LockService.getScriptLock();lock.waitLock(10000);
 try{
  var sheet=sheet16_(),existing=rows16_(sheet),keys=new Set(existing.map(function(r){return r.client+'|'+r.symbol;}));
  grid.forEach(function(v){var row={};heads.forEach(function(k,i){row[k]=v[i];});var s=String(row.symbol||'');if(!/^\d{4,6}[AB]?\.(TW|TWO)$/.test(s)||keys.has('personal|'+s))return;
   sheet.appendRow(['personal',s,safeCell16_(String(row.name||s)),safeCell16_(String(row.note||'')),String(row.active)!=='false',1]);keys.add('personal|'+s);
  });
 }finally{lock.releaseLock();}
}
