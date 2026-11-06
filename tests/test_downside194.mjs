import assert from 'node:assert/strict';
import {esc,safeLink,evidenceCard,bridgeHTML,downsideHTML,sizeAddition} from '../assets/downside194.mjs';
let n=0;function t(name,fn){fn();n++;console.log('PASS',name)}
t('HTML source is escaped',()=>{const h=evidenceCard({title:'<img src=x onerror=x>',excerpt:'<script>no</script>',url:'javascript:alert(1)'});assert(!h.includes('<img'));assert(!h.includes('<script>'));assert(!h.includes('href="javascript'));assert(h.includes('&lt;script&gt;'))});
t('safe URLs only',()=>{assert.equal(safeLink('javascript:alert(1)'),'');assert.equal(safeLink('https://www.cna.com.tw/'),'https://www.cna.com.tw/')});
t('historical pages cannot load today evidence',()=>assert.match(bridgeHTML({market_events:[{title:'FUTURE_SECRET'}]},{mode:'historical'}),/歷史/));
t('historical bridge does not expose future title',()=>assert(!bridgeHTML({market_events:[{title:'FUTURE_SECRET'}]},{mode:'historical'}).includes('FUTURE_SECRET')));
t('mismatched snapshot blocked',()=>assert.match(bridgeHTML({source_snapshot_sha256:'a'},{mode:'forward',hash:'b'}),/尚未對上/));
t('missing sidecar gives actual workflow',()=>assert.match(bridgeHTML(null,{mode:'forward'}),/Update evidence and downside research/));
t('missing metrics are not zeros',()=>assert.match(downsideHTML({state:'missing',metrics:{}}),/未取得/));
const cfg={entry:100,stop:96,target:130,cash:100000,cap:20000,risk:1000,held:0,mark:100,fraction:.25};
t('reasonable hypothetical sizing within risk',()=>{const r=sizeAddition(cfg);assert(r.shares>0);assert(r.buy<=20000);assert(r.loss<=250);assert.equal(r.expectedReturn,null);assert.equal(r.autoOrders,false)});
t('existing mark-to-stop risk cannot be reset',()=>{const r=sizeAddition({...cfg,cash:4000,cap:8000,risk:200,held:30,mark:102,fraction:1});assert.equal(r.shares,0);assert(r.existingRisk>200)});
t('no tiny position hiding fee',()=>{assert.equal(sizeAddition({...cfg,cash:4000,cap:4000,risk:200,target:106}).shares,0)});
t('no fractional or negative holdings',()=>{assert.equal(sizeAddition({...cfg,held:1.5}).shares,0);assert.equal(sizeAddition({...cfg,held:-1}).shares,0)});
t('invalid inputs rejected',()=>{assert.equal(sizeAddition({...cfg,entry:NaN}).shares,0);assert.equal(sizeAddition({...cfg,target:90}).shares,0)});
t('inputs are immutable',()=>{const s=JSON.stringify(cfg);sizeAddition(cfg);assert.equal(JSON.stringify(cfg),s)});
console.log(n+' checks passed');
