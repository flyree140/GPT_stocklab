import assert from 'node:assert/strict';
import {simulate} from '../assets/engine.mjs';
const rows=[{date:'2026-01-01',open:100,high:102,low:99,close:101,volume:10},{date:'2026-01-02',open:102,high:105,low:101,close:104,volume:10},{date:'2026-01-05',open:104,high:116,low:103,close:114,volume:10}];
const locked=simulate(rows,{date:'2026-01-01',capital:100000,days:5,stop:.05,take:.1,fee:0,tax:0,slippage:0,min_fee:0},{reveal:false});assert.equal(locked.status,'locked');
const open=simulate(rows,{date:'2026-01-01',capital:100000,days:5,stop:.05,take:.1,fee:0,tax:0,slippage:0,min_fee:0},{reveal:true});assert.equal(open.entry_date,'2026-01-02');
console.log('engine tests passed');
