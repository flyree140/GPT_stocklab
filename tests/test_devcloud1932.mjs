import assert from 'node:assert/strict';import fs from 'node:fs';import * as P from '../assets/paper-engine.mjs';import * as D from '../assets/dev1932-engine.mjs';import {DeveloperCloud} from '../assets/dev1932-cloud.mjs';
const read=n=>JSON.parse(fs.readFileSync(new URL('../assets/'+n,import.meta.url)));const snap=read('paper-demo-snapshot.json'),cal=read('paper-calendar.json');const ctx={at:snap.generated_at,generatedAt:snap.generated_at,asOf:snap.as_of,path:'fixture',hash:'fixture',mode:'demo',cal};
const settings={...D.DEFAULT,capital:4000,budget:4000,maxLoss:200,goal:150};const batch=await D.confirmBatch(D.prepare(snap,ctx,settings),ctx,settings);
class Fake extends DeveloperCloud{constructor(){super({clientId:'test'});this.sheet='test';this.rows=[['批次ID','版本','SHA256','序號','總段數','JSON']];this.app='1932'}async api(url,method='GET',body=null){if(url.includes('googleapis.com/drive/'))return {appProperties:{stocklabDeveloper:this.app}};if(method==='POST'&&url.includes(':append')){this.rows.push(...body.values);return {ok:true}}return {values:structuredClone(this.rows)}}}
let n=0;async function t(s,fn){await fn();n++;console.log('PASS',s)}
await t('store and readback verified',async()=>{const c=new Fake;const o=await c.saveBatches([batch]);assert.ok(o.ok);assert.equal((await c.readBatches())[0].id,batch.id)});
await t('retries idempotent no duplicate rows',async()=>{const c=new Fake;await c.saveBatches([batch]);const count=c.rows.length;await c.saveBatches([batch]);assert.equal(c.rows.length,count)});
await t('changed cloud chunk refused',async()=>{const c=new Fake;await c.saveBatches([batch]);c.rows[1][5]=c.rows[1][5].replace('虛擬','實際');if(c.rows[1][5]===P.canonical(batch))c.rows[1][5]+='x';await assert.rejects(()=>c.readBatches())});
await t('different ledger namespace blocked',async()=>{const c=new Fake;c.app='19';await assert.rejects(()=>c.select('abc'),/不是開發者/)});
await t('older local version cannot overwrite cloud',async()=>{const c=new Fake;await c.saveBatches([D.trash(batch)]);await assert.rejects(()=>c.saveBatches([batch]),/版本較新/)});
await t('same revision conflict blocked',async()=>{const c=new Fake;await c.saveBatches([batch]);const changed=P.copy(batch);changed.createdAt='2026-01-01T00:00:00Z';await assert.rejects(()=>c.saveBatches([changed]),/衝突/)});
console.log(JSON.stringify({passed:n,total:n,google_network:'mocked'}));
