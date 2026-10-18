const common=new Set('que para uma com como pelo pela foi era isso aqui sobre senhor chefe jarvis registro registrado lembranca lembrancas memoria memorias encontrei relacionado relacionadas proposta anterior podemos vamos deve usar'.split(' '));
function words(text){return new Set((String(text||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().match(/[a-z0-9]{3,}/g)||[]).filter(word=>!common.has(word)));}

export function focusForNarration(items,text){
  const spoken=words(text);let best=0,index=-1,tied=false,matches=0;
  items.forEach((item,i)=>{
    const evidence=words(item.title+' '+item.detail);
    const score=[...spoken].reduce((sum,word)=>sum+Number(evidence.has(word)),0);
    if(score>=2)matches++;
    if(score>best){best=score;index=i;tied=false;}else if(score===best)tied=true;
  });
  // A batch containing several memories cannot identify the current spoken one.
  return best>=2&&!tied&&matches===1?index:-1;
}

export function voiceEnvelope(current,target,dt){
  target=Number.isFinite(target)?Math.max(0,Math.min(1,target)):0;
  const elapsed=Number.isFinite(dt)?Math.max(0,Math.min(.25,dt)):0;
  return current+(target-current)*(1-Math.exp(-elapsed*(target>current?18:7)));
}
