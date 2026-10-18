import {UltronWorld} from './ultron/ultron.mjs';
import {focusBlend} from './environment-rig.mjs';

const canvas=document.getElementById('ultron-canvas'),hud=document.getElementById('ultron-projection');
let world,environment={visible:true,staging:new URLSearchParams(location.search).get('staged')==='1',motion:'full'},payload={state:{phase:'idle'}},narrationState={},spoken='',cancelled=false;
const revealed=new Set();let topic='';
let lastSignature='',captionNode,captionStart=0,audioElapsed=0;
function updateCameraFocus(active){
  if(!world?.ready)return;
  const previous=window.ultronCameraState;
  if(previous?.to===(active?1:0))return;
  const now=Date.now();
  const focus={from:focusBlend(previous,now,environment.motion==='reduced'),to:active?1:0,
    at:now,duration:1800,anchor:[...world.root.position.toArray(),world.root.scale.x]};
  window.ultronCameraState=focus;environment={...environment,ultronFocus:focus};world.host(environment);
  dispatchEvent(new Event('ultron-camera'));
}
function captionText(){const duration=Math.max(.35,spoken.split(/\s+/).length*.32);return spoken.slice(0,Math.min(spoken.length,Math.floor((audioElapsed-captionStart)/duration*spoken.length)+1));}
const fields=[['cpu_percent','CPU',/cpu|processador/i,'%'],['memory_percent','Memoria',/mem[oó]ria|ram/i,'%'],['disk_percent','Disco',/disco|armazenamento/i,'%'],['process_count','Processos',/processos/i,''],['connection_count','Conexoes',/conex[oõ]es|rede/i,'']];
const stages={telemetry:'Recursos do computador',defender:'Microsoft Defender',threats:'Deteccoes ativas',firewall:'Firewall',services:'Servicos',startup:'Inicializacao',events:'Eventos criticos',complete:'Consultas concluidas'};

function line(label,value,kind=''){
  const row=document.createElement('div');row.className='ultron-reading '+kind+(String(value).length>16?' detailed':'');
  const term=document.createElement('span'),data=document.createElement('strong');term.textContent=label;data.textContent=value;
  row.append(term,data);return row;
}
function render(){
  const state=payload.state||{},active=state.phase&&state.phase!=='idle';hud.hidden=!active||environment.visible===false||environment.staging;
  const data=narrationState;
  const signature=JSON.stringify([hud.hidden,state.phase,state.scan?.running,state.scan?.progress,state.confirmation_pending,state.operations,data,spoken,cancelled,[...revealed]]);
  if(signature===lastSignature)return;lastSignature=signature;
  hud.replaceChildren();if(hud.hidden)return;
  const heading=document.createElement('h2');heading.textContent='PROTOCOLO ULTRON';hud.append(heading);
  if(state.scan?.running){hud.append(line(stages[state.scan.stage]||'Analisando',`${state.scan.progress||0}%`));return;}
  for(const [key,label,,unit] of fields){
    if(!revealed.has(key))continue;
    const value=data.telemetry?.[key];hud.append(line(label,typeof value==='number'?`${Math.round(value)}${unit}`:'Indisponivel'));
  }
  if(revealed.has('protection'))for(const item of (data.findings||[]).filter(f=>['defender','firewall','threats'].includes(f.id))){
    const detail=item.detail;
    let value='Consulta indisponivel';
    if(detail&&typeof detail==='object')value=item.id==='defender'?(detail.enabled&&detail.realtime?'Protecao em tempo real ativa':'Protecao indisponivel'):item.id==='firewall'?`${detail.enabled}/${detail.count} perfis ativos`:`${detail.active} deteccoes ativas`;
    hud.append(line(item.title,value,item.severity));
  }
  if(revealed.has('vault')){
    hud.append(line('Cofre',`${data.vault_count||0} copias`));
    for(const backup of (data.vault||[]).slice(0,3))hud.append(line(new Date(backup.created_at).toLocaleDateString('pt-BR'),`${backup.file_count} arquivos`));
  }
  if(revealed.has('simulation'))hud.append(line('Simulacoes isoladas',String(data.simulation_count||0)));
  if(revealed.has('findings'))for(const item of (data.findings||[]).filter(f=>f.severity!=='info').slice(0,3))hud.append(line(item.title,typeof item.detail==='string'?item.detail:'Observacao real; consulte o Jarvis',item.severity));
  if(spoken&&!cancelled){captionNode=document.createElement('p');captionNode.textContent=captionText();hud.append(captionNode);}else captionNode=null;
  if(state.confirmation_pending){const pending=document.createElement('small');pending.textContent='Aguardando sua resposta ao Jarvis';hud.append(pending);}
  if(revealed.has('operations'))for(const operation of (state.operations||[]).slice(-2))hud.append(line('Operacao do Windows',({running:'Em andamento',pending:'Aguardando',completed:'Comando concluido',failed:'Falha informada',uncertain:'Estado incerto'})[operation.state]||operation.state||'Sem conclusao confirmada'));
}
window.ultronHost=value=>{environment={...environment,...value};hud.dataset.motion=environment.motion||'full';world?.host(environment);render();};
window.updateUltron=value=>{
  if(!value?.state)return;
  payload=value;
  if(value.result){revealed.clear();topic='';spoken='';cancelled=false;narrationState=value.state;}
  window.ultronActive=value.state.phase!=='idle';
  updateCameraFocus(window.ultronActive);
  const state=value.state;world?.setState(state.phase==='scanning'?'scanning':state.phase==='idle'?'idle':'active',state.findings||[]);
  if(value.result)world?.setContext(value.result.mode==='vault'?'vault':value.result.mode==='simulation'?'simulation':'diagnostic');
  render();
};
window.advanceUltron=beat=>{
  if(Number.isFinite(beat.elapsed))audioElapsed=beat.elapsed;
  if(beat.cancelled){cancelled=true;spoken='';render();return;}
  for(const text of beat.cues||[]){
    cancelled=false;spoken=text;captionStart=audioElapsed;
    const next=/windows|varredura|integridade|reparo|executando/i.test(text)?'operations':/cofre|backup|c[oó]pia|recupera[cç][aã]o/i.test(text)?'vault':/simula[cç][aã]o|simula[cç][oõ]es/i.test(text)?'simulation':/defender|prote[cç][aã]o|seguran[cç]a|firewall|amea[cç]a/i.test(text)?'protection':fields.some(field=>field[2].test(text))?'telemetry':/observa[cç][aã]o|observa[cç][oõ]es|anomalia|press[aã]o|problema/i.test(text)?'findings':topic;
    if(next!==topic){revealed.clear();topic=next;}
    for(const [key,,pattern] of fields)if(pattern.test(text))revealed.add(key);
    if(/defender|prote[cç][aã]o|seguran[cç]a|firewall|amea[cç]a/i.test(text))revealed.add('protection');
    if(/cofre|backup|c[oó]pia|recupera[cç][aã]o/i.test(text))revealed.add('vault');
    if(/simula[cç][aã]o|simula[cç][oõ]es/i.test(text))revealed.add('simulation');
    if(/observa[cç][aã]o|observa[cç][oõ]es|anomalia|press[aã]o|problema/i.test(text))revealed.add('findings');
    if(/windows|varredura|integridade|reparo|executando/i.test(text))revealed.add('operations');
  }
  render();
  if(captionNode&&!cancelled)captionNode.textContent=captionText();
};
try{
  world=new UltronWorld(canvas,{embedded:true});world.host(environment);await world.init();
  window.updateUltron(payload);window.ultronDiagnostics=()=>({...world.diagnostics(),embedded:true,staging:environment.staging,revealed:[...revealed]});
  dispatchEvent(new Event('ultron-ready'));
}catch(error){canvas.hidden=true;hud.hidden=true;document.body.dataset.ultronError='render-unavailable';console.error('ULTRON visual indisponivel',error);}
addEventListener('pagehide',()=>world?.dispose());
