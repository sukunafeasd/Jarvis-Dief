import * as THREE from "three";
import { profileFor } from './presentation_profiles.mjs';
import { factSymbolFor, buildFactSymbol } from './fact-symbols.mjs';
import { HudSurface } from './hud-surface.mjs';
import { surfaceFor } from './projection-style.mjs';
import {buildPinnedSymbol,animatePinnedSymbol} from './pinned-symbols.mjs';
import { HolographicPanelMotion, HolographicSymbolRig } from './holographic-motion.mjs';
const hudSurface = new HudSurface(document.body);
const panelMotion = new HolographicPanelMotion();
let symbolRig = null, motionTime = 0, dismissStarted = 0, cancelledAt = 0;
let clockEpoch=Date.now(), clockMotionOrigin=0;
const $ = (id) => document.getElementById(id);
const escape = (v) =>
  String(v ?? "--").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const number = (v) =>
  Number.isFinite(v)
    ? new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(v)
    : "--";
let model = {},
  signature = "",
  group = new THREE.Group(),
  rain,
  mode = "",
  started = performance.now();
let navigationSerial = 0;
let surfaceAnimation;
let focusEnergy=0;
const pointer={x:0,y:0,inside:false};
let pointerEnergy=0, pointerTilt=new THREE.Vector2();
addEventListener('pointermove',event=>{
  const bounds=$('symbol-space').getBoundingClientRect();
  pointer.inside=event.clientX>=bounds.left && event.clientX<=bounds.right && event.clientY>=bounds.top && event.clientY<=bounds.bottom;
  pointer.x=pointer.inside?(event.clientX-bounds.left)/Math.max(1,bounds.width)*2-1:0;
  pointer.y=pointer.inside?(event.clientY-bounds.top)/Math.max(1,bounds.height)*2-1:0;
});
addEventListener('pointerleave',()=>{pointer.inside=false;pointer.x=pointer.y=0;});
window.setNewsFusion = fused => {
  const surface=document.querySelector('main');
  document.body.style.visibility=fused ? 'hidden' : '';
  document.body.style.pointerEvents=fused ? 'none' : '';
  document.body.dataset.newsFusion=String(Boolean(fused));
  if(!fused && model.kind==='news' && !reducedMotion()) {
    surfaceAnimation?.cancel();
    surfaceAnimation=surface.animate([
      {opacity:0,transform:'scale(.86)',filter:'brightness(1.5)'},
      {opacity:1,transform:'scale(1)',filter:'brightness(1)'}
    ],{duration:580,easing:'cubic-bezier(.2,.7,.2,1)'});
  }
};
const speechKey=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
function spokenOrdinal(text) {
  const normalized=speechKey(text);
  const stems=['primeir','segund','terceir','quart','quint','sext','setim','oitav','non','decim'];
  const nouns={news:'noticia|manchete|assunto',tasks:'tarefa|item',gmail:'mensagem|email|e-mail',
    whatsapp:'mensagem|conversa',calendar:'compromisso|reuniao|evento'}[model.kind] || 'item|assunto';
  const found=stems.map((stem,index)=>({index,matched:new RegExp('\\b'+stem+'[ao](?:\\s+(?:'+nouns+')(?:s)?\\b|\\s+(?:e|tem|vence|sera|vem)\\b|\\s*[:.!?])').test(normalized)})).filter(item=>item.matched);
  return found.length>1 ? -2 : found.length ? found[0].index : -1;
}
let audioElapsed = 0,
  audioStarted = false,
  cancelled = false,
  audioFallbackAt = 0,
  audioUpdated = 0,
  audioFinished = false,
  chapterStart = 0,
  segmentOffset = 0;
let narrationRequested=false;
function presentationTime() {
  if(cancelled)return audioElapsed*1000;
  return model.narrationDriven
    ? audioElapsed * 1000 +
        (audioStarted && !cancelled
          ? audioFinished
            ? performance.now() - audioUpdated
            : Math.min(240, performance.now() - audioUpdated)
          : 0)
    : performance.now() - started;
}
window.advancePresentation = (beat) => {
  if (cancelled || audioFinished || (beat.presentationId!==undefined && String(beat.presentationId)!==String(model.presentationId))) return;
  if(narrationRequested) model.narrationDriven=true;
  audioStarted = true;
  audioElapsed = segmentOffset + beat.elapsed;
  audioUpdated = performance.now();
  audioFinished = false;
  (beat.cues || []).forEach((text) => window.narratePresentation(text));
  document.body.dataset.playback = "active";
  document.body.dataset.timingDegraded=String(Boolean(beat.degraded));
};
window.cancelPresentation = () => {
  audioElapsed = presentationTime() / 1000;
  cancelledAt=performance.now();
  cancelled = true;
  document.body.dataset.playback = "cancelled";
};
window.resumePresentation = (origin=0) => {
  segmentOffset = audioElapsed-(Number.isFinite(origin)?origin:0);
  cancelled = false;
  audioStarted=false;audioFinished=false;audioUpdated=performance.now();
};
window.finishPresentation = () => {
  audioUpdated = performance.now();
  audioFinished = true;
  document.body.dataset.playback = "finished";
  reveals.forEach((reveal,index)=>{
    if(reveal.deferred){reveal.deferred=false;reveal.start=presentationTime()+Math.min(index,6)*90;}
  });
};
let reveals = [],
  lastSpoken = "",
  lastContent = "";
const reducedMotion = () => model.motion === "reduced" || model.motion !== 'full' && matchMedia('(prefers-reduced-motion: reduce)').matches;
window.holographicMotionDiagnostics = () => ({
  time:motionTime, panelTime:panelMotion.material.uniforms.time.value,
  rig:Boolean(symbolRig), rings:symbolRig?.rings.length||0,
  particles:symbolRig?.particles.geometry.attributes.phase.count||0,
  geometries:renderer?.info.memory.geometries||0,
  drawCalls:renderer?.info.render.calls||0,
  pointerEnergy, tilt:[pointerTilt.x,pointerTilt.y],
});
window.presentationStatus = () => ({
  audioElapsed,
  audioStarted,
  cancelled,
  narration: model.narrationDriven,
  motion: model.motion || "full",
});
window.dismissPresentation = () => {
  surfaceAnimation?.cancel();
  document.body.dataset.dismissing = 'true';
  document.querySelector('main').style.opacity='0';
  if(!reducedMotion()) {
    dismissStarted=performance.now();
    document.body.animate([{opacity:1},{opacity:0}],{duration:220,fill:'forwards',easing:'ease-in'});
    surfaceAnimation=document.querySelector('main').animate([{opacity:1,clipPath:'inset(0)'},
      {opacity:0,clipPath:'inset(48% 0 48% 0)'}],{duration:220,fill:'forwards',easing:'ease-in'});
  } else {
    document.body.style.opacity='0';
    document.querySelector('main').style.opacity='0';group.visible=false;
  }
};
function materializeSurface() {
  surfaceAnimation?.cancel();
  if(reducedMotion()) return;
  panelMotion.begin(performance.now());
  const surface=document.querySelector('main');
  const profile=profileFor(model.kind);
  const from=profile.assembly==='editorial' ? 'inset(0 48% 0 48%)' :
    ['envelope','bubbles'].includes(profile.assembly) ? 'inset(100% 0 0 0)' : 'inset(45% 100% 45% 0)';
  surfaceAnimation=surface.animate([{opacity:0,clipPath:from},{opacity:1,clipPath:'inset(0)'}],
    {duration:model.compact?320:480,easing:'cubic-bezier(.2,.7,.2,1)'});
}
const stagedSelector="#summary h1,#summary p,#summary .fact,.metric strong,.record h2,.record p,#details > p,.forecast strong,.forecast small,.article-source";
function textKey(node,index){return `${node.closest('.record')?.dataset.index??'summary'}:${node.tagName}:${node.className}:${index}`;}
function stageText(prior=new Map()) {
  reveals = [];
  document
    .querySelectorAll(
      stagedSelector,
    )
    .forEach((node, index) => {
      const text = node.textContent;
      if (!text) return;
      if(model.reading && node.matches('.record p') && text.length>1200){
        node.setAttribute('aria-label',text);
        return;
      }
      node.style.minHeight = node.getBoundingClientRect().height + "px";
      node.setAttribute("aria-label", text);
      const key=textKey(node,index),old=prior.get(key);
      if(old?.complete){node.textContent=text;return;}
      node.textContent = "";
      const entry={
        node,
        text,
        start: chapterStart + (model.compact ? 120 + index * 50 : 250 + index * (model.narrationDriven ? 300 : 120)),
        last: -1,
        deferred: Boolean(model.narrationDriven && !model.compact && ['gmail','whatsapp','tasks','calendar'].includes(model.kind) && node.matches('.record p')),
        target: node.closest('.record')?.dataset.index,
        key,
      };
      if(old?.text===text){entry.start=old.start;entry.deferred=old.deferred;entry.last=old.shown.length;node.textContent=old.shown;}
      reveals.push(entry);
    });
}
window.narratePresentation = (text) => {
  if(cancelled || audioFinished)return;
  const spoken = String(text).toLocaleLowerCase("pt-BR");
  if (spoken === lastSpoken) return;
  lastSpoken = spoken;
  if(['gmail','whatsapp','tasks','calendar'].includes(model.kind) && model.narrationDriven){
    const normalized=speechKey(spoken);
    let target=spokenOrdinal(normalized);
    if(target===-1){
      const candidates=(model.items||[]).map((item,index)=>({index,score:speechKey(item.title).split(/\W+/).filter(word=>word.length>=3 && !['com','para','uma','das','dos','que'].includes(word)).filter(word=>new RegExp('\\b'+word+'\\b').test(normalized)).length})).filter(item=>item.score>=2).sort((a,b)=>b.score-a.score);
      if(candidates.length && (candidates.length===1 || candidates[0].score>candidates[1].score)) target=candidates[0].index;
    }
    if(target>=0 && target<(model.items||[]).length){
      focusEnergy=.12;
      const changed=target!==(model.focus||0);
      model.focus=target;
      if(!document.querySelector(`.record[data-index="${target}"]`))render();
      reveals.forEach(reveal=>{if(Number(reveal.target)===target && reveal.deferred){reveal.deferred=false;reveal.start=presentationTime();}});
      document.querySelectorAll('.record').forEach(row=>row.classList.toggle('selected',Number(row.dataset.index)===target));
      document.querySelector(`.record[data-index="${target}"]`)?.scrollIntoView({block:'nearest',behavior:reducedMotion()?'instant':'smooth'});
      if(changed) location.hash='speech-focus-'+target+'-'+ ++navigationSerial+'-'+model.presentationId;
    }
  }
  if (model.kind === "news") {
    // Whole transcript batches may mention several articles ahead of playback.
    // Only an unambiguous semantic cue may change the currently visible article.
    let index=spokenOrdinal(spoken);
    if(index===-2) return;
    if (index < 0) {
      const matches = (model.items || []).map((item,i) => ({i, score:
        String(item.title)
          .toLowerCase()
          .split(/\s+/)
          .filter((w) => w.length > 4)
          .filter((w) => spoken.includes(w)).length})).filter(item => item.score >= 2);
      matches.sort((a,b)=>b.score-a.score);
      index = matches.length && (matches.length===1 || matches[0].score>matches[1].score) ? matches[0].i : -1;
    }
    if (
      index >= 0 &&
      index < model.items.length &&
      index !== (model.focus || 0)
    ) {
      model.focus = index;
      chapterStart = presentationTime();
      render();
      location.hash = "speech-focus-" + index + "-" + ++navigationSerial + "-" + model.presentationId;
    }
  }
  const targets = model.kind !== 'weather' ? null : spoken.includes("vento")
    ? ".metric:nth-child(2)"
    : spoken.includes("chuva")
      ? ".metric:nth-child(1)"
      : spoken.includes("grau")
        ? ".fact"
        : spoken.includes('umidade') ? '.metric:nth-child(3)' : null;
  if (targets) {
    focusEnergy=.14;
    document
      .querySelectorAll(".narrated")
      .forEach((n) => n.classList.remove("narrated"));
    document.querySelector(targets)?.classList.add("narrated");
  }
  document.body.dataset.narrating = "true";
};
function dateLabel(value) {
  if (!value) return "";
  value=String(value);
  const date = new Date(value.length === 10 ? value + "T00:00:00" : value);
  if (!Number.isFinite(date.getTime())) return value;
  return date.toLocaleString(
    "pt-BR",
    value.length === 10
      ? { day: "2-digit", month: "2-digit" }
      : {
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        },
  );
}
let renderer;
const scene = new THREE.Scene(),
  camera = new THREE.PerspectiveCamera(36, 1, 0.1, 30);
camera.position.z = 6;
const ambientLight=new THREE.HemisphereLight('#e7faff','#12222b',1.1);
const keyLight=new THREE.DirectionalLight('#fff3e9',2.5);
keyLight.position.set(-2,3,4);
const rimLight=new THREE.DirectionalLight('#55d9f0',1.25);
rimLight.position.set(3,.5,-2);
scene.add(ambientLight,keyLight,rimLight);
const microData=new Uint8Array(64*64*4);
for(let i=0;i<64*64;i++){
  const grain=190+((i*73+(i>>6)*29)%37);
  microData.set([grain,grain,grain,255],i*4);
}
const microSurface=new THREE.DataTexture(microData,64,64);
microSurface.wrapS=microSurface.wrapT=THREE.RepeatWrapping;
microSurface.repeat.set(3,3);microSurface.needsUpdate=true;
try {
  renderer = new THREE.WebGLRenderer({
    canvas: $("scene"),
    antialias: true,
    alpha: true,
    powerPreference: "low-power",
    preserveDrawingBuffer: true,
  });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.15;
  scene.add(group);
} catch (e) {
  document.body.dataset.fallback = "true";
}
function dispose() {
  // Keep the projection rig/programs alive across live updates of the same domain.
  if(symbolRig) {
    group.remove(symbolRig.group);
    if(symbolRig.kind!==model.kind || symbolRig.compact!==Boolean(model.compact) || model.error || ['news','status'].includes(model.kind)) {
      symbolRig.dispose();symbolRig=null;
    }
  }
  group.traverse((o) => {
    o.geometry?.dispose();
    if (o.material) o.material.dispose();
  });
  scene.remove(group);
  group = new THREE.Group();
  scene.add(group);
  rain = null;
}
function material(color, opacity = 1) {
  const surface=new THREE.MeshStandardMaterial({
    color,
    emissive: color,
    emissiveIntensity: 0.18,
    roughness: 0.22,
    metalness: 0.24,
    transparent: opacity < 1,
    opacity,
    depthWrite: opacity === 1,
    roughnessMap:microSurface,
    dithering:true,
  });
  surface.onBeforeCompile=shader=>{
    shader.uniforms.spatialEdge={value:new THREE.Color(profileFor(mode).secondary)};
    shader.fragmentShader='uniform vec3 spatialEdge;\n'+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <dithering_fragment>',
      'gl_FragColor.rgb += spatialEdge * pow(clamp(1.0 - abs(dot(normal, normalize(vViewPosition))), 0.0, 1.0), 3.0) * 0.075;\n#include <dithering_fragment>');
  };
  surface.customProgramCacheKey=()=> 'spatial-edge-v1';
  return surface;
}
function orb(x, y, z, r, color) {
  const o = new THREE.Mesh(
    new THREE.IcosahedronGeometry(r, 2),
    material(color),
  );
  o.position.set(x, y, z);
  group.add(o);
  return o;
}
function arc(radius, start, end, color, z = 0) {
  const pts = [];
  for (let i = 0; i <= 70; i++) {
    const a = start + ((end - start) * i) / 70;
    pts.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, z));
  }
  const o = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.65 }),
  );
  group.add(o);
  o.userData.drawCount = pts.length;
  return o;
}
function band(radius,start,length,color,z=0,thickness=.025) {
  const mesh=new THREE.Mesh(new THREE.TorusGeometry(radius,thickness,6,64,Math.max(.001,length)),material(color));
  mesh.rotation.z=start;mesh.position.z=z;group.add(mesh);return mesh;
}
function trail(points,color) {
  const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));
  const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)),new THREE.LineBasicMaterial({color,transparent:true,opacity:.45}));
  line.userData.drawCount=49;group.add(line);return line;
}
function packet(path,color,phase) {
  const item=orb(0,0,0,.045,color);
  item.userData.path=path;item.userData.phase=phase;
  return item;
}
function beveledSurface(width,height,depth,color) {
  const radius=Math.min(width,height)*.065;
  const x=width/2,y=height/2;
  const shape=new THREE.Shape();
  shape.moveTo(-x+radius,-y);
  shape.lineTo(x-radius,-y);shape.quadraticCurveTo(x,-y,x,-y+radius);
  shape.lineTo(x,y-radius);shape.quadraticCurveTo(x,y,x-radius,y);
  shape.lineTo(-x+radius,y);shape.quadraticCurveTo(-x,y,-x,y-radius);
  shape.lineTo(-x,-y+radius);shape.quadraticCurveTo(-x,-y,-x+radius,-y);
  const bevel=Math.min(depth*.2,.015);
  const geometry=new THREE.ExtrudeGeometry(shape,{depth:Math.max(.001,depth-2*bevel),
    bevelEnabled:true,bevelSize:bevel,bevelThickness:bevel,bevelSegments:2,curveSegments:5,steps:1});
  geometry.translate(0,0,-depth/2+bevel);
  const surface = new THREE.Mesh(geometry,material(color));
  surface.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 35),
    new THREE.LineBasicMaterial({color:profileFor(mode).secondary,transparent:true,opacity:.7,depthWrite:false,blending:THREE.AdditiveBlending})));
  return surface;
}
function build() {
  dispose();
  mode = model.kind;
  if(model.compact && mode!=='status') {
    group.add(buildPinnedSymbol(model));
    group.children[0].userData.pinnedSymbol=true;
    camera.position.z=4.9;
    started=performance.now();
    return;
  }
  if (mode === "status") {
    group.visible = false;
    return;
  }
  camera.position.z = mode === "news" ? 10 : model.compact ? 5.3 : ['gmail','whatsapp'].includes(mode) ? 4.2 : 4.8;
  const profile=profileFor(mode);
  const accent = profile.accent;
  if (mode === "weather") {
    const code = model.code ?? -1,
      cloudy = code > 0;
    if (code >= 0 && code <= 2) {
      const sun=orb(.64,.30,-.45,.34,model.is_day===0?'#d3dfea':'#ffad45');
      sun.userData.sun=true;
      const corona=band(.44,0,Math.PI*2,model.is_day===0?'#8faebc':'#dfad61',-.46,.008);
      corona.position.set(.64,.30,-.46);corona.userData.corona=true;
    }
    if (cloudy) {
      [
        [-0.65, 0, 0.1, 0.34],
        [-0.27, 0.18, 0.18, 0.46],
        [0.22, 0.05, 0.05, 0.43],
        [0.6, -0.02, -0.18, 0.32],
        [-0.15, -0.18, -0.1, 0.37],
      ].forEach(([x, y, z, r],index) => {
        const geometry=new THREE.SphereGeometry(r,24,14);
        const position=geometry.attributes.position;
        for(let v=0;v<position.count;v++){
          const x=position.getX(v),y=position.getY(v),z=position.getZ(v);
          const contour=1+.055*Math.sin(x*11+index)*Math.cos(y*9-z*7);
          position.setXYZ(v,x*contour,y*contour,z*contour);
        }
        geometry.computeVertexNormals();
        const cloud=new THREE.Mesh(geometry,material(code>=95?'#7694b4':'#e1edf8'));
        cloud.scale.set(1.12,.92,1);cloud.position.set(x,y,z);
        cloud.material.roughness=.55;cloud.material.metalness=0;cloud.material.emissiveIntensity=.035;
        cloud.userData.cloud=index;group.add(cloud);
      });
    }
    if (code >= 51) {
      const snow = [71, 73, 75, 77, 85, 86].includes(code);
      const count = model.compact ? 36 : code >= 95 ? 90 : code >= 71 && code <= 86 ? 35 : 65;
      const a = new Float32Array(count * (snow ? 3 : 6));
      for (let i = 0; i < count; i++) {
        const offset = i * (snow ? 3 : 6),
          x = Math.sin(i * 41.7) * 0.85,
          y = -0.05 - ((i % 17) / 17) * 0.95,
          z = Math.cos(i * 21.3) * 0.55;
        a.set([x, y, z], offset);
        if (!snow) a.set([x + 0.018, y - 0.14, z], offset + 3);
      }
      rain = new (snow ? THREE.Points : THREE.LineSegments)(
        new THREE.BufferGeometry().setAttribute(
          "position",
          new THREE.BufferAttribute(a, 3),
        ),
        new (snow ? THREE.PointsMaterial : THREE.LineBasicMaterial)({
          color: snow ? '#d4ecff' : '#45dfff',
          transparent: true,
          opacity: 0.8,
          depthWrite:false,
        }),
      );
      if (snow) rain.material.size = 0.035;
      rain.userData.snow = snow;
      group.add(rain);
    }
    const base = arc(1.12, 0, Math.PI * 2, accent, -0.1);
    base.rotation.x = 1.12;
    base.position.y = -0.87;
    base.userData.weatherBase=true;
    if(rain){
      for(let i=0;i<2;i++){
        const ripple=arc(.24+i*.18,0,Math.PI*2,'#75bbd5',0);
        ripple.rotation.x=1.12;ripple.position.y=-.87;
        ripple.userData.ripple=i;
      }
    }
    if(Number.isFinite(model.wind) && model.wind>0 && !model.compact){
      for(let i=0;i<2;i++){
        const line=trail([[-1.1,.1+i*.23,-.2],[-.55,.2+i*.23,-.5],[.25,.15+i*.23,-.5],[1.05,.28+i*.23,-.2]],'#87bacd');
        line.userData.wind=i;
      }
    }
  } else if (mode === "news") {
    // News is projected over Qt's existing primary avatar, never another core.
    document.body.dataset.secondaryCore = "false";
  } else if (mode === "gmail" || mode === "whatsapp") {
    if(mode==='gmail') {
      const shell=beveledSurface(1.38,.85,.12,'#edf4fb');group.add(shell);
      const shape=new THREE.Shape();shape.moveTo(-.69,0);shape.lineTo(.69,0);shape.lineTo(0,-.42);shape.closePath();
      const flap=new THREE.Mesh(new THREE.ShapeGeometry(shape),material('#ff484f'));
      flap.position.set(0,.42,.095);flap.userData.mailFlap=true;group.add(flap);
      const letter=beveledSurface(1.02,.68,.035,'#a8cde6');
      letter.position.set(0,.14,-.085);letter.userData.mailLetter=true;group.add(letter);
      for(let i=0;i<3;i++){
        const ink=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-.32,.37-i*.14,-.06),new THREE.Vector3(.30-i*.045,.37-i*.14,-.06)]),new THREE.LineBasicMaterial({color:'#567785',transparent:true,opacity:.45}));
        ink.userData.mailLetter=true;group.add(ink);
      }
      trail([[-.67,-.4,.075],[0,.03,.08],[.67,-.4,.075]],'#809ba8');
    } else {
      for(let i=0;i<2;i++){
        const shape=new THREE.Shape();shape.moveTo(-.53,-.18);shape.lineTo(-.53,.26);shape.quadraticCurveTo(-.53,.4,-.37,.4);
        shape.lineTo(.40,.4);shape.quadraticCurveTo(.53,.4,.53,.26);shape.lineTo(.53,-.20);shape.quadraticCurveTo(.53,-.32,.39,-.32);
        shape.lineTo(-.18,-.32);shape.lineTo(-.40,-.49);shape.lineTo(-.36,-.32);shape.lineTo(-.4,-.32);shape.closePath();
        const bubble=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:.14,bevelEnabled:true,bevelSize:.025,bevelThickness:.02,bevelSegments:3,steps:1}),material(i?'#02b98c':'#79edc6'));
        bubble.rotation.y=i?-.18:.15;
        bubble.add(new THREE.LineSegments(new THREE.EdgesGeometry(bubble.geometry,40),
          new THREE.LineBasicMaterial({color:'#b9ffe5',transparent:true,opacity:.75,depthWrite:false,blending:THREE.AdditiveBlending})));
        bubble.position.set(i?-.23:.18,i?.16:-.08,i?-.18:.10);bubble.userData.bubble=i;group.add(bubble);
      }
      for(let i=0;i<3;i++){
        const dot=orb(-.13+i*.16,.10,.24,.032,'#125b47');dot.userData.chatDot=i;
      }
    }
    for(let i=0;i<3;i++){
      const packet=orb(-.4+i*.4,.65,.15,.055,mode==='gmail'?['#ea655b','#efc968','#70a9ec'][i]:'#75e9b2');
      packet.userData.messagePacket=i;
    }
  } else if (mode === "tasks") {
    const core=orb(0,0,0,.22,accent);core.userData.taskCore=true;
    const inner=band(.36,0,Math.PI*1.65,profile.secondary,.10,.015);inner.userData.taskHalo=true;
    const count = Math.min(model.count || 0, 16);
    arc(0.78, 0, Math.PI * 2, "#304c59");
    for (let i = 0; i < count; i++) {
      const a = (i * 2 * Math.PI) / Math.max(count, 1);
      band(
        0.78,
        a + 0.08,
        (2 * Math.PI) / count - 0.16,
        i % 2 ? profile.secondary : accent,
      );
      const marker=orb(
        Math.cos(a) * 1.05,
        Math.sin(a) * 1.05,
        model.items?.[i]?.priority === "high" ? 0.22 : 0,
        0.055,
        model.items?.[i]?.priority === "high" ? "#edcd7f" : accent,
      );
      marker.userData.taskMarker=i;
    }
  } else if (mode === "system") {
    ["cpu_percent", "ram_percent", "gpu_percent"].forEach((key, i) => {
      arc(0.4 + i * 0.24, 0, Math.PI * 2, "#294451", i * 0.06);
      if (Number.isFinite(model[key]) && model[key]>0)
        band(
          0.4 + i * 0.24,
          Math.PI / 2,
          (Math.PI * 2 * Math.max(0, Math.min(100, model[key]))) / 100,
          ['#00ddff','#ff4759','#39eccd'][i],
          i * 0.06 + 0.01,
        );
    });
    orb(0, 0, 0.05, 0.15, accent);
    for (let i = 0; i < 3; i++) {
      const packet = orb(
        0.4 + i * 0.24,
        0,
        0.08 + i * 0.06,
        0.045,
        ['#00ddff','#ff4759','#39eccd'][i],
      );
      packet.userData.orbit = 0.4 + i * 0.24;
      packet.userData.activity=Number.isFinite(model[['cpu_percent','ram_percent','gpu_percent'][i]])?model[['cpu_percent','ram_percent','gpu_percent'][i]]/100:0;
    }
  } else if (mode === "calendar") {
    clockEpoch=Date.now();clockMotionOrigin=motionTime;
    for (let i = 0; i < 12; i++) {
      const a = (i * Math.PI) / 6;
      const marker = new THREE.Mesh(
        new THREE.BoxGeometry(0.025, 0.1, 0.025),
        material(i === 0 ? "#f1c979" : "#6ecebc"),
      );
      marker.position.set(Math.sin(a) * 0.94, Math.cos(a) * 0.94, 0);
      marker.rotation.z = -a;
      group.add(marker);
    }
    orb(0, 0, 0.1, 0.1, "#f1c979");
    arc(0.75, -0.25, Math.PI * 1.3, accent);
    band(.99,0,Math.PI*2,'#728fa2',-.07,.01);
    const count = Math.min(model.items?.length || 0, 8);
    for (let i = 0; i < count; i++) {
      const a = 0.2 + i * 0.4;
      orb(
        Math.cos(a) * 0.75,
        Math.sin(a) * 0.75,
        0.1,
        0.065,
        i === model.focus ? "#edcd7f" : accent,
      );
    }
    arc(0.45, 0, Math.PI * 2, "#40535b");
    const hand = new THREE.Mesh(
      new THREE.BoxGeometry(0.02, 0.53, 0.025),
      material("#f1c979"),
    );
    hand.position.y = 0.265;
    const pivot = new THREE.Group();
    pivot.add(hand);
    pivot.userData.clockHand = true;
    group.add(pivot);
    const second=new THREE.Group();
    const secondHand=new THREE.Mesh(new THREE.BoxGeometry(.009,.7,.015),material('#72c9b5'));
    secondHand.position.y=.35;second.add(secondHand);second.userData.secondHand=true;group.add(second);
  } else if (mode === "memory") {
    const nodes = [
      [-0.7, 0.2, 0],
      [-0.2, 0.5, 0.2],
      [0.45, 0.28, -0.1],
      [0.6, -0.3, 0.15],
      [-0.1, -0.5, 0],
    ];
    nodes.forEach(([x, y, z], i) => {
      const node=orb(x,y,z,i===0?.13:.08,i===0?profile.secondary:accent);node.userData.memoryNode=i;
      if (i) {
        const points = [
          new THREE.Vector3(...nodes[0]),
          new THREE.Vector3(x, y, z),
        ];
        group.add(
          new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(points),
            new THREE.LineBasicMaterial({
              color: accent,
              transparent: true,
              opacity: 0.55,
            }),
          ),
        );
        const curve=new THREE.LineCurve3(new THREE.Vector3(...nodes[0]),new THREE.Vector3(x,y,z));
        packet(curve,profile.secondary,i*.21);
      }
    });
  } else if (mode === "search") {
    const lens = arc(0.63, 0, Math.PI * 2, "#69dab8");
    lens.rotation.y = 0.18;
    const handle = new THREE.Mesh(
      new THREE.CylinderGeometry(0.04, 0.04, 0.6, 8),
      material("#f1c979"),
    );
    handle.position.set(0.63, -0.63, 0);
    handle.rotation.z = 0.78;
    group.add(handle);
    orb(0, 0, 0.1, 0.08, accent);
    const sweep=band(.45,0,Math.PI*.55,profile.secondary,.08,.012);sweep.userData.searchSweep=true;
  } else if (mode === "files") {
    for (let i = 0; i < 3; i++) {
      const slab = beveledSurface(.9,.12,.65,["#51b4dc", "#64d5ae", "#e8c77c"][i]);
      slab.position.set(i * 0.12, -0.35 + i * 0.28, -i * 0.16);
      slab.rotation.y = 0.45;
      slab.userData.fileSlab=i;
      const edges=new THREE.LineSegments(new THREE.EdgesGeometry(slab.geometry),new THREE.LineBasicMaterial({color:'#d2e7ef',transparent:true,opacity:.24}));
      slab.add(edges);
      group.add(slab);
    }
    arc(1.02, 0.3, Math.PI * 1.4, accent);
  } else if (factSymbolFor(model)) {
    const symbol = buildFactSymbol(factSymbolFor(model));
    while (symbol.children.length) group.add(symbol.children[0]);
  } else {
    for (let i = 0; i < 3; i++) {
      const slab = beveledSurface(1.45,.82,.035,["#4099b7", "#57bca1", "#d4b46c"][i]);
      slab.position.set(i * 0.13, i * 0.08, -i * 0.24);
      slab.rotation.y = -0.16;
      group.add(slab);
    }
  }
  if(!['news','status'].includes(mode) && !model.error) {
    symbolRig ||= new HolographicSymbolRig(model);
    symbolRig.group.position.set(0,0,0);symbolRig.group.rotation.set(0,0,0);symbolRig.group.scale.setScalar(1);
    group.add(symbolRig.group);
  }
  group.children.forEach((node) => {
    node.userData.basePosition = node.position.clone();
    node.userData.baseScale = node.scale.clone();
    node.userData.baseRotation = node.rotation.clone();
  });
  started = performance.now();
}
function metric(label, value) {
  return `<div class="metric"><strong>${escape(value)}</strong><span>${escape(label)}</span></div>`;
}
function syncMetadata() {
  const source=$('source').textContent.trim();
  $('metadata').textContent=source;
  $('metadata').hidden=!source || surfaceFor(model)==='embedded' || model.kind==='status' || Boolean(model.compact);
}
function render(preserveText=false) {
  const prior=new Map();
  if(preserveText)document.querySelectorAll(stagedSelector).forEach((node,index)=>{
    const original=node.getAttribute('aria-label')??node.textContent;
    const pending=reveals.find(entry=>entry.node===node);
    prior.set(textKey(node,index),{text:original,shown:node.textContent,complete:node.textContent===original,start:pending?.start,deferred:pending?.deferred});
  });
  document.body.dataset.revealed='false';
  dismissStarted=0;
  surfaceAnimation?.cancel();
  document.body.getAnimations().forEach(animation=>animation.cancel());
  document.body.style.opacity='1';
  document.body.dataset.dismissing='false';
  const profile=profileFor(model.kind);
  document.body.dataset.kind = model.kind;
  document.body.dataset.surface = surfaceFor(model);
  document.body.dataset.refresh = model.refreshTransaction ? 'true' : 'false';
  document.body.dataset.assembly = profile.assembly;
  document.body.dataset.animationProfile = profile.motion;
  document.body.dataset.compact = model.compact ? 'true' : 'false';
  document.body.dataset.framed = model.framed ? 'true' : 'false';
  document.body.dataset.motion = model.motion || "full";
  document.body.dataset.factSymbol = model.compact ? '' : factSymbolFor(model);
  group.visible = true;
  document.querySelector("main").style.opacity = "1";
  document.body.dataset.layout = !model.compact && ["news", "status"].includes(model.kind) ? "editorial" : ['gmail','whatsapp'].includes(model.kind) ? 'communications' : "object";
  document.documentElement.style.setProperty(
    "--accent",
    profile.accent,
  );
  document.documentElement.style.setProperty('--secondary',profile.secondary);
  $("title").textContent = model.title || "";
  $("summary").innerHTML = "";
  $("metrics").innerHTML = "";
  $("details").innerHTML = "";
  $("source").textContent = model.source || "";
  syncMetadata();
  if (model.error) {
    $("summary").innerHTML =
      `<h1>${escape(model.city || model.title)}</h1><p>${escape(model.error)}</p>`;
    return;
  }
  if (model.kind === "status") {
    group.visible = false;
    const unavailable=model.items?.length && model.items.every(item=>['warning','error'].includes(item.status));
    $("summary").innerHTML = `<h1>${unavailable?'Algumas fontes indisponíveis':'Estou me atualizando'}</h1><p class="muted">${escape(model.completed || 0)} / ${escape(model.total || 0)} fontes verificadas</p>`;
    if(model.refreshTransaction){
      const total=Math.max(0,Number(model.total)||0),done=Math.max(0,Math.min(total,Number(model.completed)||0));
      const percent=total?Math.round(done/total*100):0;
      const current=(model.items||[]).filter(item=>item.status==='working').map(item=>item.title).join(' · ');
      $("summary").innerHTML=`<h1>${escape(current ? 'Consultando '+current : unavailable ? 'Fontes indisponíveis' : total ? 'Consultas concluídas' : 'Preparando as consultas')}</h1><div class="refresh-progress" role="progressbar" aria-label="Fontes consultadas" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><span style="width:${percent}%"></span></div><p class="muted">${done} / ${total} fontes consultadas · ${percent}%</p>`;
    }
    $("details").innerHTML = (model.items || []).map((item) => `<div class="check-row" data-state="${["ok","warning","error"].includes(item.status) ? item.status : "working"}"><span class="check-mark" aria-hidden="true"></span><div><h2>${escape(item.title)}</h2><p>${escape(item.detail)}</p></div></div>`).join("");
    document.body.dataset.kind = "status";
    return;
  } else if (model.kind === "weather") {
    $("summary").innerHTML =
      `<p class="muted">${model.region ? escape(model.region)+' · ' : ''}${model.period === "tomorrow" ? "AMANHÃ · MÁXIMA PREVISTA" : "AGORA"}</p><h1>${escape(model.city)}</h1><div class="fact">${number(model.temperature)}°</div><p>${escape(model.condition)}</p>`;
    $("metrics").innerHTML =
      metric("CHANCE DE CHUVA", number(model.rain) + "%") +
      metric("VENTO", number(model.wind) + " km/h") +
      metric("UMIDADE", number(model.humidity) + "%");
    $("details").innerHTML =
      '<div class="forecast">' +
      (model.forecast || [])
        .slice(0, model.period === "week" ? 7 : 4)
        .map(
          (d) =>
            `<div><small>${escape(dateLabel(d.date) || '--')}</small><strong>${number(d.max)}°</strong><small>${number(d.min)}° · ${number(d.rain)}%</small></div>`,
        )
        .join("") +
      "</div>";
    $("source").textContent = `Open-Meteo · ${model.observed || ""}`;
  } else if (model.kind === "system") {
    $("summary").innerHTML = model.compact ? `<h1>Sistema</h1><p>CPU ${number(model.cpu_percent)}%</p><p>RAM ${number(model.ram_percent)}%</p>` : "<h1>Estado da máquina</h1>";
    $("metrics").innerHTML =
      metric("CPU", number(model.cpu_percent) + "%") +
      metric("RAM", number(model.ram_percent) + "%") +
      metric("GPU", number(model.gpu_percent) + "%") +
      metric("TEMPERATURA", number(model.cpu_temp_c) + "°C");
    $("details").innerHTML =
      `<p>${number(model.ram_used_gb)} / ${number(model.ram_total_gb)} GB de memória</p><p class="muted">${escape(model.uptime)} ligado · ${escape(model.process_count)} processos</p>`;
  } else {
    const items = model.items || [];
    $("summary").innerHTML =
      model.kind === "tasks"
        ? `<div class="fact">${Number.isFinite(model.count)?String(model.count).padStart(2, "0"):'--'}</div><p>PENDENTES</p>`
        : `<h1>${model.kind === "calendar" ? "Seus compromissos" : model.kind === "news" ? model.compact ? 'Notícias' : "EDIÇÃO " + String((model.focus || 0) + 1).padStart(2, "0") + " / " + items.length : escape(model.title)}</h1>`;
    if (!items.length)
      $("details").innerHTML =
        `<p class="muted">${model.emptyText ? escape(model.emptyText) : model.text ? escape(model.text).replace(/\n/g, "<br>") : model.kind === "calendar" ? "Nenhum compromisso local cadastrado." : model.kind === "tasks" ? "Nenhuma tarefa pendente." : "Nenhum item disponível."}</p>`;
    const limit=model.compact?2:20,first=Math.floor((model.focus||0)/limit)*limit;
    items.slice(first,first+limit).forEach((item, local) => {
      const i=first+local;
      const row = document.createElement("div");
      row.dataset.index=i;
      row.style.setProperty('--order',Math.min(i,6));
      row.className = "record" + (i === (model.focus || 0) ? " selected" : "");
      row.setAttribute("role", "article");
      row.setAttribute("aria-label", `Selecionar ${item.title}`);
      const detail =
        model.kind === "news" && i !== (model.focus || 0)
          ? ""
          : dateLabel(item.due) || item.detail || "";
      row.innerHTML = `<span class="index">${escape(item.value || String(i + 1).padStart(2, "0"))}</span><div><h2>${escape(item.title)}</h2><p class="muted">${escape(detail)}${item.priority === "high" ? " · PRIORITÁRIA" : ""}</p></div>`;
      if (model.kind === "news") {
        const source = document.createElement("small");
        source.className = "article-source";
        source.textContent = item.source || "Fonte não informada";
        row.append(source);
      }
      if (
        model.kind === "news" &&
        i === (model.focus || 0) &&
        /^data:image\/(jpeg|png|webp);base64,/.test(item.image || "")
      ) {
        const image = document.createElement("img");
        image.src = item.image;
        image.alt = item.title;
        image.className = "news-banner";
        row.prepend(image);
      }
      $("details").append(row);
    });
  }
  document.body.dataset.kind = model.kind;
  document.body.dataset.count = model.items?.length || 0;
  syncMetadata();
  stageText(prior);
}
window.updateCore = (value) => {
  if(!value || typeof value!=='object' || Array.isArray(value))return;
  if (value.visible === false) {
    model.visible = false;
    return;
  }
  if (!value.kind) {
    model.visible = value.visible !== false;
    if(model.visible && model.kind && document.body.dataset.dismissing==='true') render();
    return;
  }
  const rows=input=>Array.isArray(input)?input.filter(item=>item && typeof item==='object' && !Array.isArray(item)):[];
  value={...value,items:rows(value.items),forecast:rows(value.forecast)};
  value.focus=Math.max(0,Math.min(value.items.length-1,Math.trunc(Number(value.focus)||0)));
  const next = JSON.stringify(value);
  const identity = JSON.stringify([
    value.presentationId,
    value.kind,
    value.city,
    value.period,
    value.count,
    value.items?.map((i) => i.title),
  ]);
  if (identity !== lastContent) {
    narrationRequested=Boolean(value.narrationDriven);
    audioElapsed = Number.isFinite(value.audioOrigin) ? value.audioOrigin : 0;
    audioStarted = false;
    audioFinished = false;
    audioUpdated = 0;
    chapterStart = audioElapsed * 1000;
    segmentOffset = 0;
    cancelled = false;
    lastSpoken = "";
    focusEnergy=0;
    audioFallbackAt = performance.now() + 8000;
    lastContent = identity;
  }
  const fresh = identity !== JSON.stringify([model.presentationId,model.kind,model.city,model.period,model.count,model.items?.map(i=>i.title)]);
  model = { ...value, visible: true };
  const reopening=document.body.dataset.dismissing==='true';
  if (next !== signature || reopening) {
    const oldKind = mode;
    signature = next;
    render(!fresh&&!reopening);
    if (oldKind !== model.kind || value.rebuild !== false) {
      const oldStarted = started;
      build();
      if (oldKind === model.kind) started = oldStarted;
    }
    if(fresh || reopening) materializeSurface();
    if(document.body.dataset.newsFusion !== String(Boolean(value.newsFusion))) window.setNewsFusion(Boolean(value.newsFusion));
  }
};
let previous = performance.now();
let timer;
let renderWidth=0,renderHeight=0;
function frame() {
  const now = performance.now(),
    dt = Math.min(0.1, (now - previous) / 1000);
  previous = now;
  document.body.dataset.hudMotion = reducedMotion() || model.visible === false || document.hidden ? 'reduced' : 'full';
  if (model.visible !== false && !document.hidden) hudSurface.update(model, innerWidth, innerHeight);
  if (
    model.narrationDriven &&
    !audioStarted &&
    !cancelled &&
    now > audioFallbackAt
  ) {
    model.narrationDriven = false;
    started = now;
    document.body.dataset.playback = "audio-fallback";
    reveals.forEach(reveal=>{reveal.deferred=false;});
  }
  const clock = presentationTime();
  document.body.dataset.revealed =
    clock - chapterStart > 650 ? "true" : "false";
  reveals.forEach((r) => {
    if(r.deferred) return;
    const count = Math.max(
      0,
      Math.min(r.text.length, Math.floor((clock - r.start) * (model.compact ? .08 : model.kind==='news' ? .028 : .040))),
    );
    if (count !== r.last) {
      r.node.textContent = r.text.slice(0, count);
      r.last = count;
    }
  });
  reveals = reveals.filter((r) => r.last < r.text.length);
  if (renderer && model.visible !== false && !document.hidden) {
    if(!reducedMotion() && !cancelled) motionTime+=dt;
    if(reducedMotion()) {
      pointerEnergy=0;pointerTilt.set(0,0);
    } else if(!cancelled) {
      pointerEnergy=THREE.MathUtils.damp(pointerEnergy,pointer.inside?1:0,5,dt);
      pointerTilt.x=THREE.MathUtils.damp(pointerTilt.x,pointer.x*.11,5,dt);
      pointerTilt.y=THREE.MathUtils.damp(pointerTilt.y,pointer.y*.08,5,dt);
    }
    const profile=profileFor(mode);
    if(!cancelled)focusEnergy=reducedMotion()?0:THREE.MathUtils.damp(focusEnergy,0,2,dt);
    const lightTarget=(['weather','memory'].includes(mode)?1.65:2.0)+focusEnergy;
    if(!cancelled) {
      keyLight.intensity=reducedMotion()?lightTarget:THREE.MathUtils.damp(keyLight.intensity,lightTarget,3,dt);
      if(reducedMotion()) rimLight.color.set(profile.accent);
      else rimLight.color.lerp(new THREE.Color(profile.accent),Math.min(1,dt*2));
    }
    const w = innerWidth,
      h = innerHeight;
    if(w!==renderWidth || h!==renderHeight){
      renderer.setSize(w,h,false);renderWidth=w;renderHeight=h;
    }
    const zone =
      model.kind === "news" && !model.compact
        ? { left:0, width:w, bottom: h, height: h }
        : $("symbol-space").getBoundingClientRect();
    renderer.setViewport(zone.left, h - zone.bottom, zone.width, zone.height);
    camera.aspect = zone.width / Math.max(1,zone.height);
    camera.updateProjectionMatrix();
    const assemblyTime=(cancelled?cancelledAt:now)-started;
    const assembled = Math.max(0, Math.min(1, assemblyTime / 650));
    const exiting=dismissStarted?Math.min(1,(now-dismissStarted)/220):0;
    group.scale.setScalar(
      (reducedMotion() ? 1 : 0.8 + 0.2 * (1 - Math.pow(1 - assembled, 3)))*Math.max(.01,1-exiting),
    );
    if(exiting===1) group.visible=false;
    group.rotation.y = !reducedMotion() && ['gmail','whatsapp'].includes(mode) ? .12+.05*Math.sin(motionTime*.7) : 0;
    group.rotation.y+=pointerTilt.x;group.rotation.x=pointerTilt.y;
    group.children.forEach((object, index) => {
      const progress = reducedMotion()
        ? 1
        : Math.max(0, Math.min(1, (assemblyTime - index * (model.compact?6:16)) / 650));
      object.scale
        .copy(object.userData.baseScale || new THREE.Vector3(1, 1, 1))
        .multiplyScalar(0.01 + 0.99 * (1 - Math.pow(1 - progress, 3)));
      if (object.userData.drawCount)
        object.geometry.setDrawRange(
          0,
          Math.floor(object.userData.drawCount * progress),
        );
      if (object.userData.basePosition) {
        object.position.copy(object.userData.basePosition);
        if(!reducedMotion()){
          const unresolved=1-progress;
          const base=object.userData.basePosition;
          if(mode==='weather'){
            object.position.x-=base.x*unresolved*.35;
            object.position.y-=base.y*unresolved*.35;
            object.position.z+=.28*unresolved;
          } else if(mode==='tasks' || mode==='memory'){
            object.position.multiplyScalar(1-.65*unresolved);
          } else if(mode==='gmail' || mode==='whatsapp'){
            object.position.y-=.28*unresolved;
            object.position.z+=.24*unresolved;
          } else object.position.z+=.55*unresolved;
        }
      }
      if(object.userData.baseRotation) object.rotation.copy(object.userData.baseRotation);
      if(object.userData.pinnedSymbol)animatePinnedSymbol(object,motionTime,reducedMotion());
      const t=motionTime, strength=model.compact ? .9 : 1;
      if (!reducedMotion() && object.userData.cloud!==undefined) {
        object.position.x += strength*.10*Math.sin(t*.5+index*1.2);
        object.position.y += strength*.055*Math.cos(t*.7+index);
        object.rotation.y += .12*Math.sin(t*.3+index);
        object.material.emissiveIntensity = model.code>=95 ? .12+.06*Math.pow(Math.max(0,Math.sin(t*.35)),18) : .10;
      }
      if(!reducedMotion() && object.userData.sun){object.rotation.y+=t*.18;object.material.emissiveIntensity=.28+.09*Math.sin(t*1.2);}
      if(!reducedMotion() && object.userData.corona) object.scale.multiplyScalar(1+.09*Math.sin(t*1.1));
      if(!reducedMotion() && object.userData.ripple!==undefined){
        const phase=(t*.32+object.userData.ripple*.5)%1;
        object.scale.multiplyScalar(.5+phase*1.2);object.material.opacity=.42*(1-phase);
      }
      if(!reducedMotion() && object.userData.wind!==undefined){
        object.geometry.setDrawRange(Math.floor((t*.18+index*.2)%1*18),30);
      }
      if(!reducedMotion() && object.userData.mailFlap) object.rotation.x=-.28-.55*(.5+.5*Math.sin(t*.95));
      if(!reducedMotion() && object.userData.mailLetter) object.position.y+=.18*(.5+.5*Math.sin(t*.95));
      if(!reducedMotion() && object.userData.bubble!==undefined){
        object.position.y+=strength*.045*Math.sin(t*1.1+index);
        object.rotation.y+=.10*Math.sin(t*.7+index);
      }
      if(!reducedMotion() && object.userData.chatDot!==undefined) object.scale.multiplyScalar(.7+.3*(.5+.5*Math.sin(t*2.2-object.userData.chatDot*.9)));
      if (!reducedMotion() && object.userData.messagePacket !== undefined) {
        const phase = (t*.35+object.userData.messagePacket/3)%1;
        if (mode==='gmail') object.position.y += phase*.3;
        else object.position.x += .12*Math.sin(phase*Math.PI*2);
        object.material.opacity = .35+.65*Math.sin(phase*Math.PI);
        object.material.transparent = true;
      }
      if(!reducedMotion() && object.userData.taskHalo) object.rotation.z+=t*.13*strength;
      if(!reducedMotion() && object.userData.taskCore) object.rotation.y+=t*.15*strength;
      if(!reducedMotion() && object.userData.taskMarker!==undefined){
        object.position.z+=.06*strength*Math.sin(t*.9+index*1.7);
        object.material.emissiveIntensity=.20+.06*Math.sin(t*.9+index);
      }
      if (!reducedMotion() && object.userData.orbit) {
        const angle = t*Math.max(0,object.userData.activity)*.55*strength+index;
        object.position.x = Math.cos(angle) * object.userData.orbit;
        object.position.y = Math.sin(angle) * object.userData.orbit;
      }
      if (object.userData.clockHand) {
        const date = new Date(clockEpoch+(reducedMotion()?0:motionTime-clockMotionOrigin)*1000);
        object.rotation.z =
          (-Math.PI * 2 * (date.getMinutes() + date.getSeconds() / 60)) / 60;
      }
      if(object.userData.secondHand && !reducedMotion()) {
        const date=new Date(clockEpoch+(motionTime-clockMotionOrigin)*1000);object.rotation.z=-Math.PI*2*(date.getSeconds()+date.getMilliseconds()/1000)/60;
      }
      if(!reducedMotion() && object.userData.fileSlab!==undefined){
        object.position.y+=.045*strength*Math.sin(t*.7+index*1.4);
        object.position.x+=.035*strength*Math.cos(t*.7+index);
      }
      if(!reducedMotion() && object.userData.memoryNode!==undefined) object.material.emissiveIntensity=.16+.12*(.5+.5*Math.sin(t*.9+index));
      if(!reducedMotion() && object.userData.path) object.position.copy(object.userData.path.getPoint((t*.16*strength+object.userData.phase)%1));
      if(!reducedMotion() && object.userData.searchSweep) object.rotation.z+=t*.85*strength;
      if(!reducedMotion() && mode==='data' && object.isMesh) object.position.z+=.05*strength*Math.sin(t*.7+index);
      if(!reducedMotion() && object.userData.factOrbit!==undefined) object.rotation.y+=.12*Math.sin(t*.35+index);
      if(!reducedMotion() && object.userData.factGlyph) {
        const beat=t*1.7+object.userData.glyphIndex*Math.PI;
        if(object.userData.factGlyph==='steps') {
          object.position.y+=.06*Math.sin(beat);object.rotation.y+=.09*Math.sin(beat);
        } else if(object.userData.factGlyph==='flame') {
          object.scale.y*=1+.06*Math.sin(t*1.8);object.rotation.z+=.025*Math.sin(t*1.3);
        }
        object.material.emissiveIntensity=.9+.18*Math.sin(beat);
      }
    });
    if (rain && !reducedMotion() && !cancelled) {
      const p = rain.geometry.attributes.position;
      for (let i = 0; i < p.count; i += rain.userData.snow ? 1 : 2) {
        let y = p.getY(i) - dt * (rain.userData.snow ? 0.24 : 1.35);
        if (y < -1.04) y = -0.05;
        p.setY(i, y);
        if (!rain.userData.snow) p.setY(i + 1, y - 0.14);
      }
      p.needsUpdate = true;
    }
    symbolRig?.update(motionTime,reducedMotion(),model,focusEnergy+pointerEnergy*.22,reducedMotion()?1:assembled);
    panelMotion.update(model,motionTime,cancelled?cancelledAt:now,w,h,reducedMotion(),focusEnergy);
    renderer.info.autoReset=false;
    renderer.info.reset();
    renderer.autoClear=false;
    renderer.clear();
    renderer.render(scene, camera);
    renderer.setViewport(0,0,w,h);
    renderer.clearDepth();
    renderer.render(panelMotion.scene,panelMotion.camera);
    document.body.dataset.motionTime=String(reducedMotion()?0:motionTime.toFixed(3));
    document.body.dataset.animationTime = Math.round(now);
    document.body.dataset.drawCalls = renderer.info.render.calls;
    document.body.dataset.geometries = renderer.info.memory.geometries;
    document.body.dataset.textures = renderer.info.memory.textures;
    document.body.dataset.lightCount='3';
  }
  document.body.dataset.ready = "true";
  timer = setTimeout(
    frame,
    model.visible === false || document.hidden
      ? 250
      : clock < 2500 || document.body.dataset.playback === "active"
        ? 16
        : symbolRig && !reducedMotion() && !cancelled ? 33 : 80,
  );
}
addEventListener("pagehide", () => {
  surfaceAnimation?.cancel();
  clearTimeout(timer);
  dispose();
  microSurface.dispose();
  hudSurface.dispose();
  panelMotion.dispose();
  symbolRig?.dispose();symbolRig=null;
  renderer?.dispose();
});
frame();
