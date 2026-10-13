import * as THREE from "three";
import { buildCore } from "./core-model.mjs";
import { coreProfile } from './core-profiles.mjs';
import { addCoreSurfaces } from './core-surface.mjs';
import { createCoreMotion } from './core-motion.mjs';
import { NewsCoreProjection } from './news-core.mjs';
import {entranceDistance} from './environment-rig.mjs';
let news = null,framesRendered=0;

const staged=new URLSearchParams(location.search).get('staged')==='1';
let state = { phase: "idle", level: 0, color: "#ff303b", visible: true },environment={staging:staged};
let renderer;
try {
  renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
    powerPreference: "default",
    preserveDrawingBuffer: !staged,
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
let appliedColor = "",
  previous = performance.now(),
  time = 0,
  level = 0,
  restVisibility = 1,
  timer=null;
let pointerStart = null,
  gestureSerial = 0,
  touchUntil = 0;
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
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / Math.max(1, innerHeight);
  camera.userData.baseDistance=Math.max(7.7,2.35/(Math.tan(THREE.MathUtils.degToRad(camera.fov*.5))*camera.aspect));
  camera.position.z=camera.userData.baseDistance+entranceDistance(environment.entrance,Date.now(),state.motion==='reduced');
  camera.updateProjectionMatrix();
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
function frame() {
  timer=null;
  const now = performance.now(),
    dt = Math.min(0.1, (now - previous) / 1000);
  previous = now;
  if (state.visible && !document.hidden) {
    core.root.visible=!environment.staging;
    camera.position.z=camera.userData.baseDistance+entranceDistance(environment.entrance,Date.now(),state.motion==='reduced');
    camera.updateMatrixWorld();
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
    renderer.render(scene, camera);
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
  if(!state.visible||document.hidden||state.motion==='reduced')return;
  timer = setTimeout(
    frame,
    state.visible && !document.hidden
      ? state.phase === "idle" || state.resting
        ? 50
        : 16
      : 250,
  );
}
let lastUpdate='';
window.updateCore = (value) => {
  const signature=JSON.stringify(value);if(signature===lastUpdate)return;lastUpdate=signature;
  state = { ...state, ...value };
  if(!state.visible){clearTimeout(timer);timer=null;return;}
  if(state.motion==='reduced'){clearTimeout(timer);frame();return;}
  if(timer===null)timer=setTimeout(frame,0);
};
window.updateEnvironment=value=>{
  const entering=environment.staging && value.staging===false;
  environment={...environment,...value};
  if(state.visible&&!document.hidden&&(entering||state.motion==='reduced')){clearTimeout(timer);frame();}
};
window.updateNewsCore = value => {
  if (!value || !Array.isArray(value.items) || !value.items.length) {
    news?.dispose();news=null;state.newsFusion=false;
  } else if (value.mode !== 'front' || news) {
    news ||= new NewsCoreProjection(core.root,core.texture);
    news.invalidate=()=>{if(state.visible&&!document.hidden&&state.motion==='reduced')frame();};
    news.update(value);state.newsFusion=true;
  }
  clearTimeout(timer);timer=null;
  if(state.visible&&!document.hidden)frame();
};
window.newsCoreDiagnostics=()=>news?.diagnostics() || {phase:'inactive',rows:0,images:0};
document.addEventListener('visibilitychange',()=>{clearTimeout(timer);if(!document.hidden&&state.visible){previous=performance.now();frame();}});
window.hologramDiagnostics=()=>({framesRendered,coreVisible:core.root.visible,phase:motion.state.phase,energy:motion.state.energy,level:motion.state.level,
  assembly:motion.state.assembly,drawCalls:renderer.info.render.calls,geometries:renderer.info.memory.geometries,
  textures:renderer.info.memory.textures,visible:state.visible,projection:!!state.projection,
  palette:{structure:surfaces.membrane.material.uniforms.tint.value.getHexString(),heart:core.energySurface.material.uniforms.tint.value.getHexString()},
  nodes:surfaces.nodes.count,orbit:core.orbit.rotation.y,cue:motion.state.cue,cueActive:motion.state.cueTime>0,
  environmentMode:environment.mode||'assistant',travel:entranceDistance(environment.entrance,Date.now(),state.motion==='reduced')});
addEventListener("pagehide", () => {
  clearTimeout(timer);
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
// Compile/upload while the native distant hub covers the loading surface.
if(staged) {
  camera.position.z=camera.userData.baseDistance+24;
  motion.step(0,{...state,motion:'reduced'});
  renderer.render(scene,camera);
  renderer.clear();
  motion.state.assembly=1;
}
frame();
