import test from 'node:test';
import assert from 'node:assert/strict';
import {NeuralLifecycle} from '../core/spatial/neural/lifecycle.mjs';
const item={id:'notes/test',detail:'Stored test fact'};
function advance(lifecycle,seconds,options){for(let t=0;t<seconds;t+=.05)lifecycle.step(.05,options);}

test('topic clarification enters brain without fabricated fragments and times out',()=>{
 const l=new NeuralLifecycle();l.update({pending:true,requestId:'ask'});
 l.update({requestId:'ask',active:true,awaitingTopic:true,items:[item],depth:'quick'});
 advance(l,3,{speaking:true});assert.equal(l.progress,1);assert.equal(l.items.length,0);assert.equal(l.awaitingTopic,true);
 advance(l,10,{});assert.equal(l.target,1);advance(l,24,{});assert.equal(l.progress,0);assert.equal(l.awaitingTopic,false);
});

test('actual subject replaces clarification and cancellation rejects late results',()=>{
 const l=new NeuralLifecycle();l.update({pending:true,requestId:'ask'});l.update({requestId:'ask',active:true,awaitingTopic:true});
 l.step(.1,{reduced:true});assert.equal(l.progress,1);
 l.update({pending:true,requestId:'answer'});l.update({requestId:'answer',active:true,items:[item]});
 assert.equal(l.awaitingTopic,false);assert.equal(l.items.length,1);
 l.cancel();l.update({requestId:'answer',active:true,awaitingTopic:true});assert.equal(l.awaitingTopic,false);
});
test('stale results cannot resurrect cancelled retrieval',()=>{
 const l=new NeuralLifecycle();l.update({pending:true,requestId:'a'});l.cancel();l.update({requestId:'a',active:true,items:[item]});assert.equal(l.target,0);
});

test('no results and storage failure still form brain with honest status, then return',()=>{
 for(const outcome of ['empty','unavailable']){
  const l=new NeuralLifecycle();l.update({pending:true,requestId:'done'});l.update({requestId:'done',active:true,items:[],outcome,depth:'quick'});
  advance(l,3,{speaking:true});assert.equal(l.progress,1);assert.equal(l.items.length,0);assert.equal(l.outcome,outcome);
  advance(l,3,{});assert.equal(l.target,1);advance(l,6,{});assert.equal(l.progress,0);assert.equal(l.outcome,null);
 }
});
test('full journey is gradual, then returns after speech and hold',()=>{
 const l=new NeuralLifecycle();l.update({pending:true,requestId:'a'});l.update({requestId:'a',active:true,items:[item],depth:'deep'});
 advance(l,2.4,{speaking:true});assert.ok(l.progress>.49&&l.progress<.52);advance(l,2.5,{speaking:true});assert.equal(l.progress,1);
 advance(l,3,{speaking:true});assert.equal(l.target,1);advance(l,5,{});advance(l,2,{});assert.equal(l.progress,0);assert.equal(l.items.length,0);
});
test('low frame rates do not turn a five second morph into thirty seconds',()=>{
 const l=new NeuralLifecycle();l.update({pending:true,requestId:'slow'});l.update({requestId:'slow',active:true,items:[item],depth:'deep'});
 for(let i=0;i<16;i++)l.step(.3,{speaking:true});assert.ok(l.progress>.99);
});
test('failure, timeout and reduced motion remain bounded',()=>{
 const l=new NeuralLifecycle();l.update({pending:true,requestId:'x'});advance(l,28,{});assert.equal(l.progress,0);
 l.update({pending:true,requestId:'y'});l.update({requestId:'y',active:true,items:[item]});l.step(.1,{reduced:true});assert.equal(l.progress,1);
 l.update({requestId:'y',active:false});advance(l,7,{});assert.equal(l.progress,0);
});
test('new retrieval supersedes old response and malformed data',()=>{
 const l=new NeuralLifecycle();l.update({pending:true,requestId:'a'});l.update({pending:true,requestId:'b'});l.update({requestId:'a',active:true,items:[item]});assert.equal(l.target,.12);
 l.update({requestId:'b',active:true,items:[null,{},item]});assert.equal(l.items.length,1);
});
test('one hundred retrieval and cancellation cycles do not retain items',()=>{
 const l=new NeuralLifecycle();
 for(let i=0;i<100;i++){
   l.update({pending:true,requestId:String(i)});l.update({requestId:String(i),active:true,items:[item],depth:'quick'});
   advance(l,6,{speaking:true});assert.equal(l.progress,1);l.cancel();advance(l,7,{});
   assert.equal(l.progress,0);assert.equal(l.items.length,0);
 }
});
