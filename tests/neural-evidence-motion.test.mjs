import test from 'node:test';
import assert from 'node:assert/strict';
import {focusForNarration,voiceEnvelope} from '../core/spatial/neural/evidence-motion.mjs';
const items=[{title:'Forja',detail:'Biblioteca local para salvar projetos criados.'},{title:'Forja',detail:'Motor Codex com conta individual conectada.'}];
test('narrated evidence focuses only its related fragment',()=>{
 assert.equal(focusForNarration(items,'A biblioteca local permite salvar projetos.'),0);
 assert.equal(focusForNarration(items,'O motor Codex usa sua conta individual.'),1);
 assert.equal(focusForNarration(items,'Encontrei lembrancas relacionadas, senhor.'),-1);
 assert.equal(focusForNarration(items,'O Spotify esta aberto.'),-1);
 assert.equal(focusForNarration(items,'Forja'),-1);
 assert.equal(focusForNarration([items[0],items[0]],'Biblioteca local para projetos'),-1);
 assert.equal(focusForNarration(items,'Biblioteca local para projetos. Depois, o motor Codex usa a conta individual.'),-1);
});
test('voice light has a bounded attack and smooth release',()=>{
 let level=voiceEnvelope(0,1,.016);assert.ok(level>0&&level<.4);
 for(let i=0;i<30;i++)level=voiceEnvelope(level,1,.016);
 assert.ok(level>.99);const release=voiceEnvelope(level,0,.016);assert.ok(release>0&&release<level);
 assert.equal(voiceEnvelope(0,NaN,.1),0);assert.equal(voiceEnvelope(0,1,NaN),0);
});
