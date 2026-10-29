import assert from 'node:assert/strict';
import {canonical19,hash19,record19,recordRow19,parseRows19,dedupe19,materialize19,settingsHeads19,SheetsJournal19,SHEETS19,HEADERS19,SCOPE19} from '../assets/cloud19.mjs';
import {defaultAccount,accountState,profile} from '../assets/life-engine.mjs';
const cal={start:'2026-01-01',end:'2026-12-31',closed:[]};let n=0;
async function test(name,f){await f();n++;console.log('PASS',name)}
const base={account:defaultAccount(),profile:profile({}),favorites:[]};
const validate=b=>{profile(b.profile);accountState(b.account.events,{},cal,'2026-10-22')};
const ev={id:'e1',date:'2026-10-20',recordedAt:'2026-10-20T10:00:00Z',type:'deposit',amount:4000};
const rec=await record19('event',ev,ev.id,'device1',ev.recordedAt);
const settings=await record19('settings',{profile:base.profile,favorites:[],parents:[]},'s1','device1');
await test('canonical serialization order stable',()=>{assert.equal(canonical19({z:1,a:{d:2,c:3}}),canonical19({a:{c:3,d:2},z:1}));assert.throws(()=>canonical19({x:NaN}))});
await test('row round trip verifies hash',async()=>{assert.deepEqual(await parseRows19([recordRow19(rec)]),[rec])});
await test('edited sheet body detected',async()=>{const row=recordRow19(rec);row[4]=JSON.stringify({...ev,amount:5000});await assert.rejects(()=>parseRows19([row]),/雜湊/) });
await test('repeat append de-duplicates by ID',()=>{assert.equal(dedupe19([rec,rec]).length,1)});
await test('same id different payload is refused',async()=>{const r=await record19('event',{...ev,amount:100},ev.id,'d1',ev.recordedAt);assert.throws(()=>dedupe19([rec,r]),/相同ID/)});
await test('remote ledger recover without local event',()=>{const result=materialize19([rec,settings],base,validate);assert.equal(result.account.events[0].amount,4000)});
await test('overspending concurrent withdrawals rejected',async()=>{const a=await record19('event',{id:'w1',date:'2026-10-21',recordedAt:'2026-10-21T10:00:00Z',type:'withdraw',amount:3000},'w1','a');const b=await record19('event',{id:'w2',date:'2026-10-21',recordedAt:'2026-10-21T10:01:00Z',type:'withdraw',amount:3000},'w2','b');assert.throws(()=>materialize19([rec,a,b,settings],base,validate),/提款超過/) });
const s2=await record19('settings',{profile:{...base.profile,goal:200},favorites:[],parents:['s1']},'s2','d1');
const s3=await record19('settings',{profile:{...base.profile,goal:300},favorites:[],parents:['s1']},'s3','d2');
await test('settings forks detected',()=>{assert.equal(settingsHeads19([settings,s2,s3]).length,2);assert.throws(()=>materialize19([settings,s2,s3],base,validate),/衝突/)});
await test('explicit settings resolution preserves history',async()=>{const s4=await record19('settings',{profile:base.profile,favorites:[],parents:['s2','s3']},'s4','d1');const result=materialize19([rec,settings,s2,s3,s4],base,validate);assert.equal(result.profile.goal,150);assert.equal(result.account.events.length,1)});
await test('oversize cell rejected before upload',async()=>{const r=await record19('plan',{note:'x'.repeat(41000)},'big','d');assert.throws(()=>recordRow19(r),/超過/)});
function mock(){let rows=[],calls=[];return {get rows(){return rows},get calls(){return calls},fetch:async(url,opt={})=>{calls.push({url,...opt});let body={};
 if(url.includes('/spreadsheets/')&&url.includes(':append')){rows.push(...JSON.parse(opt.body).values);body={updates:{updatedRows:1}}}
 else if(url.includes('/values/')&&(opt.method||'GET')==='GET')body={values:[HEADERS19,...rows]};
 else if(url.endsWith('/v4/spreadsheets'))body={spreadsheetId:'sheet_test',spreadsheetUrl:'https://docs.google.com/spreadsheets/d/sheet_test/edit'};
 else if(url.includes('?fields=spreadsheetId'))body={sheets:SHEETS19.map(title=>({properties:{title}}))};
 else if(url.includes('/drive/v3/files?'))body={files:[]};
 return {ok:true,status:200,json:async()=>body};}}}
await test('Google writes request RAW and no public permissions',async()=>{const m=mock();const c=new SheetsJournal19({fetcher:m.fetch});c.rateWaitMs=0;c.token='TEST_ONLY';c.expires=Date.now()+3600000;await c.create();assert.ok(m.calls.some(r=>r.url.includes('/spreadsheets')));assert.ok(!m.calls.some(r=>r.url.includes('/permissions')));assert.ok(m.calls.filter(r=>r.url.includes('values:batchUpdate')).every(r=>JSON.parse(r.body).valueInputOption==='RAW'))});
await test('sync uploads then confirms by reading back',async()=>{const m=mock(),statuses=[];const c=new SheetsJournal19({fetcher:m.fetch,onStatus:s=>statuses.push(s)});c.rateWaitMs=0;c.token='TEST_ONLY';c.expires=Date.now()+3600000;c.sheet='sheet_test';const result=await c.sync([rec,settings],validate,base);assert.equal(result.bundle.account.events.length,1);assert.equal(statuses.at(-1),'synced');const before=m.rows.length;await c.sync([rec,settings],validate,base);assert.equal(m.rows.length,before)});
await test('unacknowledged append never called synced',async()=>{const statuses=[];const c=new SheetsJournal19({fetcher:async()=>({ok:true,status:200,json:async()=>({values:[HEADERS19]})}),onStatus:s=>statuses.push(s)});c.rateWaitMs=0;c.token='TEST_ONLY';c.expires=Date.now()+3600000;c.sheet='sheet_test';await assert.rejects(()=>c.sync([rec],validate,base),/未完整確認/);assert.equal(statuses.at(-1),'error');assert.ok(!statuses.includes('synced'))});
await test('expired token stops network',async()=>{let called=false;const c=new SheetsJournal19({fetcher:async()=>{called=true}});c.token='TEST_ONLY';c.expires=Date.now()-1;await assert.rejects(()=>c.api('https://sheets.googleapis.com/v4/spreadsheets'),/過期/);assert.equal(called,false)});
await test('API cannot send authorization to arbitrary URL',async()=>{const c=new SheetsJournal19();c.token='TEST_ONLY';c.expires=Date.now()+3600000;await assert.rejects(()=>c.api('https://example.com/steal'),/不允許/)});
await test('private field scope only',()=>assert.equal(SCOPE19,'https://www.googleapis.com/auth/drive.file'));
await test('disconnect forgets token and current sheet',()=>{const c=new SheetsJournal19();c.token='TEST_ONLY';c.sheet='sheet_test';c.disconnect();assert.equal(c.token,null);assert.equal(c.sheet,null)});
await test('write cap stops accidental high volume',async()=>{const c=new SheetsJournal19();c.token='TEST_ONLY';c.expires=Date.now()+3600000;c.dayCalls=1000;await assert.rejects(()=>c.api('https://sheets.googleapis.com/v4/spreadsheets'),/1000/) });
console.log(`${n} cloud tests passed (mock API, not a real Google account)`);
