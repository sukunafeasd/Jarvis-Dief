import * as THREE from "three";
import { buildCore } from "./core-model.mjs";
import { coreProfile } from './core-profiles.mjs';
import { addCoreSurfaces } from './core-surface.mjs';
import { createCoreMotion } from './core-motion.mjs';
import { NewsCoreProjection } from './news-core.mjs';
import {sceneDistance} from './environment-rig.mjs';
import {installForgeTransition} from './forge-transition.mjs';
import {NeuralForm} from './neural/form.mjs';
let news = null,framesRendered=0;
let neural=null,neuralWarmTimer=null,reducedNeuralTimer=null;

const staged=new URLSearchParams(location.search).get('staged')==='1';
let state = { phase: "idle", level: 0, color: "#ff303b", visible: true },environment={staging:staged};
let renderer;
try {
  renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
    powerPreference: "high-performance",
    preserveDrawingBuffer: false,
  });
  renderer.setPixelRatio(Math.min(devicePixelRatio, innerWidth>=2560?1:1.5));
  renderer.setClearColor("#00060a",0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  document.body.appendChild(renderer.domElement);
  renderer.domElement.addEventListener("webglcontextlost", () => {
    document.body.dataset.error = "context-lost";
    state.visible = false;
  });
} catch (error) {
  document.body.dataset.error = "webgl";
  throw error;
}
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 50);
camera.position.z = 7.7;
const core = buildCore("cyan", false);
const surfaces=addCoreSurfaces(core);
const motion=createCoreMotion(core,surfaces);
scene.add(core.root);
const forgeTransition=installForgeTransition({scene,camera,renderer,core,getState:()=>state});
let appliedColor = "",
  previous = performance.now(),
  time = 0,
  level = 0,
  restVisibility = 1,
  timer=null;
let pointerStart = null,
  gestureSerial = 0,
  touchUntil = 0;
let renderWidth=0,renderHeight=0;
renderer.domElement.style.touchAction = "none";
renderer.domElement.style.cursor = "grab";
const raycaster = new THREE.Raycaster();
const hitSphere = new THREE.Sphere();
function hitsCore(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  raycaster.setFromCamera(new THREE.Vector2(
    (event.clientX - rect.left) / rect.width * 2 - 1,
    1 - (event.clientY - rect.top) / rect.height * 2,
  ), camera);
  hitSphere.center.copy(core.root.position);
  hitSphere.radius = (core.root.userData.interactionRadius||1.95) * core.root.scale.x;
  return raycaster.ray.intersectsSphere(hitSphere);
}
renderer.domElement.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || !hitsCore(event)) return;
  pointerStart = { x: event.clientX, y: event.clientY };
  renderer.domElement.setPointerCapture(event.pointerId);
});
renderer.domElement.addEventListener("pointerup", (event) => {
  if (!pointerStart) return;
  const moved =
    Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) >
    12;
  const x = Math.max(0, Math.min(1, event.clientX / innerWidth)),
    y = Math.max(0, Math.min(1, event.clientY / innerHeight));
  if (moved || hitsCore(event)) {
    touchUntil = performance.now() + 600;
    location.hash = `gesture-${moved ? "move" : "touch"}-${x.toFixed(3)}-${y.toFixed(3)}-${++gestureSerial}`;
  }
  pointerStart = null;
});
renderer.domElement.addEventListener("pointercancel", () => { pointerStart = null; });
const materialOpacities = new Map();
const controlledMaterials=new Set([core.points.material,core.radial.material,...core.pulses.children.map(node=>node.material),...core.beacons.children.map(node=>node.material)]);
core.root.traverse(node => {
  if (node.material && !materialOpacities.has(node.material))
    materialOpacities.set(node.material, node.material.opacity);
});
function resize() {
  if(innerWidth<1 || innerHeight<1)return;
  if(renderWidth!==innerWidth||renderHeight!==innerHeight){
    renderer.setSize(innerWidth, innerHeight);renderWidth=innerWidth;renderHeight=innerHeight;
  }
  camera.aspect = innerWidth / Math.max(1, innerHeight);
  camera.userData.baseDistance=Math.max(7.7,2.35/(Math.tan(THREE.MathUtils.degToRad(camera.fov*.5))*camera.aspect));
  camera.position.z=camera.userData.baseDistance+sceneDistance(environment,Date.now(),state.motion==='reduced');
  camera.updateProjectionMatrix();
  if(renderWidth&&materialOpacities.size)frame(performance.now(),true);
}
addEventListener("resize", resize);
resize();
function recolor(color) {
  if (color === appliedColor) return;
  appliedColor = color;
  const tint = new THREE.Color(color);
  const pale=tint.clone().lerp(new THREE.Color('#ffe3d7'),.27);
  const structural=tint.clone().lerp(new THREE.Color('#6f8b98'),.045);
  const neutral=tint.clone().lerp(new THREE.Color('#ffcc9a'),.32);
  const heartNodes=new Set();core.heart.traverse(node=>heartNodes.add(node));
  core.root.traverse((node) => {
    if (node.userData.newsProjection) return;
    const resolved=heartNodes.has(node)?neutral:node===surfaces.membrane?structural:node===surfaces.nodes?pale:tint;
    if (node.material?.color) node.material.color.copy(resolved);
    if (node.material?.uniforms?.tint)
      node.material.uniforms.tint.value.copy(resolved);
    const colors = node.geometry?.attributes?.color;
    if (colors) {
      for (let i = 0; i < colors.count; i++) {
        const c = tint.clone().lerp(pale, (i % 11) / 15);
        colors.setXYZ(i, c.r, c.g, c.b);
      }
      colors.needsUpdate = true;
    }
  });
}
function frame(now=performance.now(),force=false) {
  clearTimeout(reducedNeuralTimer);reducedNeuralTimer=null;
  cancelAnimationFrame(timer);
  timer=null;
  if(innerWidth<1 || innerHeight<1)return;
  const travelling=!environment.staging&&sceneDistance(environment,Date.now(),state.motion==='reduced')>.001;
  const interval=travelling||neural?.lifecycle.active||!['idle','sleeping'].includes(state.phase)?1000/60:50;
  if(!force&&!travelling&&state.motion!=='reduced'&&now-previous<interval-1){
    if(state.visible&&!document.hidden)timer=requestAnimationFrame(frame);
    return;
  }
  const elapsed=Math.max(0,(now-previous)/1000);
  const dt = Math.min(0.1,elapsed);
  previous = now;
  if (state.visible && !document.hidden) {
    const context=renderer.getContext();
    if(!context.drawingBufferWidth || !context.drawingBufferHeight){timer=requestAnimationFrame(frame);return;}
    if(forgeTransition.active){timer=requestAnimationFrame(frame);return;}
    core.root.visible=true;
    camera.position.z=camera.userData.baseDistance+sceneDistance(environment,Date.now(),state.motion==='reduced')+(neural?.lifecycle.progress||0)*1.6;
    camera.updateMatrixWorld();
    neural?.restore();
    const profile = motion.step(dt,{...state,environmentMode:environment.mode});
    restVisibility=profile.rest;time=profile.time;level=profile.level;
    materialOpacities.forEach((opacity, material) => {
      const gain=environment.mode==='focus'?.55:environment.mode==='analysis'?1.25:environment.mode==='execution'?1.4:1;
      if(!material.uniforms&&!controlledMaterials.has(material))material.opacity=Math.min(1,opacity*restVisibility*profile.assembly*gain);
    });
    // Phase/level-controlled materials override the passive structure budget.
    core.points.material.opacity=(profile.luminosity*.84+level*.12)*restVisibility*profile.assembly;
    core.radial.material.opacity=(.035+level*.3)*restVisibility;
    recolor(coreProfile(state.phase).color||state.color);
    if (now < touchUntil && state.motion!=='reduced')
      core.heart.scale.multiplyScalar(
        1 + 0.08 * Math.sin(((touchUntil - now) / 600) * Math.PI),
      );
    core.beacons.children.forEach(node=>node.material.opacity=(.28+level*.35)*restVisibility*profile.assembly);
    if (news?.step(dt, state)) {
      news.dispose();news=null;state.newsFusion=false;
    }
    neural?.step(dt,state,camera,elapsed,appliedColor);
    if(neural?.lifecycle.progress>.01)neural.render(camera);
    else renderer.render(scene, camera);
    framesRendered++;
    document.body.dataset.phase = state.phase;
    document.body.dataset.drawCalls = renderer.info.render.calls;
    document.body.dataset.ready = "true";
    document.body.dataset.restScale = core.root.scale.x;
    document.body.dataset.restDepth = core.root.position.z;
    document.body.dataset.orbitAngle = core.orbit.rotation.y;
    document.body.dataset.assembly=profile.assembly;
    document.body.dataset.geometries=renderer.info.memory.geometries;
    document.body.dataset.textures=renderer.info.memory.textures;
    document.body.dataset.motion=state.motion||'full';
  }
  if(!state.visible||document.hidden)return;
  if(state.motion==='reduced'){
    // Lifecycle deadlines still advance without a continuous animation loop.
    if(neural?.lifecycle.active)reducedNeuralTimer=setTimeout(()=>frame(performance.now(),true),250);
    return;
  }
  timer = requestAnimationFrame(frame);
}
let lastUpdate='';
window.updateCore = (value) => {
  const signature=JSON.stringify(value);if(signature===lastUpdate)return;lastUpdate=signature;
  state = { ...state, ...value };
  if(!state.visible){cancelAnimationFrame(timer);timer=null;clearTimeout(reducedNeuralTimer);reducedNeuralTimer=null;return;}
  if(state.motion==='reduced'){frame(performance.now(),true);return;}
  if(timer===null)timer=requestAnimationFrame(frame);
};
window.updateEnvironment=value=>{
  const entering=environment.staging && value.staging===false;
  environment={...environment,...value};
  if(state.visible&&!document.hidden&&(entering||state.motion==='reduced'))frame(performance.now(),true);
};
window.updateNewsCore = value => {
  if(value?.items?.length)neural?.cancel();
  if (!value || !Array.isArray(value.items) || !value.items.length) {
    news?.dispose();news=null;state.newsFusion=false;
  } else if (value.mode !== 'front' || news) {
    news ||= new NewsCoreProjection(core.root,core.texture);
    news.invalidate=()=>{if(state.visible&&!document.hidden&&state.motion==='reduced')frame();};
    news.update(value);state.newsFusion=true;
  }
  cancelAnimationFrame(timer);timer=null;
  if(state.visible&&!document.hidden)frame(performance.now(),true);
};
window.newsCoreDiagnostics=()=>news?.diagnostics() || {phase:'inactive',rows:0,images:0};
window.updateNeuralMemory=payload=>{
  if(payload?.active||payload?.pending){neural ||= new NeuralForm(scene,core,renderer);news?.dispose();news=null;}
  neural?.update(payload);
  if(state.visible&&!document.hidden){previous=performance.now();frame(previous,true);}
};
window.cancelNeuralMemory=()=>{neural?.cancel();if(state.visible&&!document.hidden)frame(performance.now(),true);};
window.narrateNeuralMemory=text=>neural?.narrate(text);
window.neuralMemoryDiagnostics=()=>({active:neural?.lifecycle.active||false,requestId:neural?.lifecycle.lastRequestId||null,progress:neural?.lifecycle.progress||0,items:neural?.lifecycle.items.length||0,awaitingTopic:neural?.lifecycle.awaitingTopic||false,outcome:neural?.lifecycle.outcome||null,voice:neural?.uniforms.uVoice.value||0,focus:neural?.focus??-1,cortexAlignment:neural?.cortexAlignment||0,deformedSurfaces:neural?.deformedSurfaces||0});
function prepareNeuralWhenIdle(){
  neuralWarmTimer=null;
  if(neural)return;
  if(environment.staging||document.hidden||!state.visible||forgeTransition.active||sceneDistance(environment,Date.now(),state.motion==='reduced')>.01||!['idle','listening'].includes(state.phase)){
    neuralWarmTimer=setTimeout(prepareNeuralWhenIdle,1500);return;
  }
  // Allocate and compile after arrival, not while the first memory is being spoken.
  neural=new NeuralForm(scene,core,renderer);
  previous=performance.now();frame(previous,true);
}
document.addEventListener('visibilitychange',()=>{cancelAnimationFrame(timer);timer=null;clearTimeout(reducedNeuralTimer);reducedNeuralTimer=null;if(!document.hidden&&state.visible){previous=performance.now();frame(performance.now(),true);}});
window.hologramDiagnostics=()=>({framesRendered,camera:camera.position.toArray(),staging:Boolean(environment.staging),coreVisible:core.root.visible,phase:motion.state.phase,energy:motion.state.energy,level:motion.state.level,
  assembly:motion.state.assembly,drawCalls:renderer.info.render.calls,geometries:renderer.info.memory.geometries,
  textures:renderer.info.memory.textures,visible:state.visible,projection:!!state.projection,
  palette:{structure:surfaces.membrane.material.uniforms.tint.value.getHexString(),heart:core.energySurface.material.uniforms.tint.value.getHexString()},
  nodes:surfaces.nodes.count,orbit:core.orbit.rotation.y,cue:motion.state.cue,cueActive:motion.state.cueTime>0,
  scheduler:'animation-frame',cameraActive:!environment.staging&&sceneDistance(environment,Date.now(),state.motion==='reduced')>.001,
  environmentMode:environment.mode||'assistant',travel:sceneDistance(environment,Date.now(),state.motion==='reduced')});
addEventListener("pagehide", () => {
  clearTimeout(neuralWarmTimer);
  clearTimeout(reducedNeuralTimer);
  cancelAnimationFrame(timer);
  neural?.dispose();neural=null;
  news?.dispose();news=null;
  const geometries = new Set(),
    materials = new Set();
  core.root.traverse((node) => {
    if(node.isInstancedMesh)node.dispose();
    if (node.geometry) geometries.add(node.geometry);
    if (node.material) materials.add(node.material);
  });
  geometries.forEach((item) => item.dispose());
  materials.forEach((item) => item.dispose());
  core.texture.dispose();
  renderer.dispose();
});
// Prepare the real distant core before the host reveals the completed scene.
if(staged && innerWidth>0 && innerHeight>0 && renderer.getContext().drawingBufferWidth && renderer.getContext().drawingBufferHeight) {
  camera.position.z=camera.userData.baseDistance+24;
  motion.step(0,{...state,motion:'reduced'});
  renderer.render(scene,camera);
  motion.state.assembly=1;
}
frame();
neuralWarmTimer=setTimeout(prepareNeuralWhenIdle,5000);
