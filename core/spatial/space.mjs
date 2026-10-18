import * as THREE from 'three';
import {SolarSystem} from './solar-system.mjs';
import {fillPlanetFacts} from './planet-facts.mjs';
import {rigTarget,frameBudget,clamp,observatoryCamera} from './environment-rig.mjs';
import {installForgeTransition} from './forge-transition.mjs';

let state={visible:true,motion:'full',phase:'idle',mode:'assistant',level:0,staging:new URLSearchParams(location.search).get('staged')==='1'};
let renderer,timer,last=0,time=0,frames=0,backdrop,solar,disposed=false;
let fps=0,frameSamples=0,sampleTime=0,quality=1,slowSince=0,fastSince=0;
let ambient=.72,gridVisibility=.018;
let renderWidth=0,renderHeight=0,renderRatio=0;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(48,1,.1,220);
camera.position.z=3;
const stars=new THREE.Group();scene.add(stars);
let seed=72691;
const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
const positions=[],colors=[],sizes=[];
for(let i=0;i<1500;i++) {
  positions.push((random()-.5)*64,(random()-.5)*40,-6-random()*90);
  const shade=new THREE.Color().setHSL(.08+random()*.56,.08+random()*.14,.58+random()*.35);
  colors.push(shade.r,shade.g,shade.b);sizes.push(.5+random()*1.7);
}
const geometry=new THREE.BufferGeometry();
geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
geometry.setAttribute('size',new THREE.Float32BufferAttribute(sizes,1));
const material=new THREE.ShaderMaterial({vertexColors:true,transparent:true,depthWrite:false,
  uniforms:{pixelRatio:{value:1},time:{value:0},visibility:{value:.72}},
  vertexShader:`attribute float size; varying vec3 tint; varying float shimmer; uniform float pixelRatio; uniform float time;
    void main(){tint=color;shimmer=.85+.15*sin(time*.4+position.x*1.3+position.z);vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=size*pixelRatio*clamp(26./-p.z,.6,2.);}`,
  fragmentShader:`varying vec3 tint;varying float shimmer;uniform float visibility;void main(){float d=length(gl_PointCoord-.5);float a=1.-smoothstep(.08,.5,d);gl_FragColor=vec4(tint,a*visibility*shimmer);}`});
stars.add(new THREE.Points(geometry,material));
const textures=[],technical=new THREE.Group();scene.add(technical);
technical.position.set(0,0,-17);
const gridPositions=[];
for(let i=-12;i<=12;i++){gridPositions.push(i,-8,0,i,8,0,-12,i*.65,0,12,i*.65,0);}
const gridGeometry=new THREE.BufferGeometry();gridGeometry.setAttribute('position',new THREE.Float32BufferAttribute(gridPositions,3));
const grid=new THREE.LineSegments(gridGeometry,new THREE.LineBasicMaterial({color:'#368caa',transparent:true,opacity:.018,depthWrite:false}));technical.add(grid);
const constellationPoints=[];
for(let i=0;i<32;i++) {
  const x=(random()-.5)*24,y=(random()-.5)*14;
  constellationPoints.push(x,y,-2,x+.3+random()*.7,y+.3+random()*.7,-2.1);
}
const networkGeometry=new THREE.BufferGeometry();networkGeometry.setAttribute('position',new THREE.Float32BufferAttribute(constellationPoints,3));
const network=new THREE.LineSegments(networkGeometry,new THREE.LineBasicMaterial({color:'#65d0d4',transparent:true,opacity:0,depthWrite:false}));technical.add(network);
const signal=new THREE.Mesh(new THREE.RingGeometry(1.1,1.115,96),new THREE.MeshBasicMaterial({color:'#65d7e6',side:THREE.DoubleSide,transparent:true,opacity:0,depthWrite:false}));
signal.position.z=-11;scene.add(signal);
const musicPoints=Array.from({length:161},(_,i)=>new THREE.Vector3(Math.cos(i/160*Math.PI*2)*2.2,Math.sin(i/160*Math.PI*2)*2.2,-11));
const musicGeometry=new THREE.BufferGeometry().setFromPoints(musicPoints);
const music=new THREE.Line(musicGeometry,new THREE.LineBasicMaterial({color:'#76bfa9',transparent:true,opacity:0,depthWrite:false}));scene.add(music);
const flowGeometry=new THREE.BufferGeometry();flowGeometry.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(6),3));
const flow=new THREE.Line(flowGeometry,new THREE.LineBasicMaterial({color:'#63d6d1',transparent:true,opacity:0,depthWrite:false}));scene.add(flow);
const packetGeometry=new THREE.BufferGeometry();packetGeometry.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(3),3));
const packet=new THREE.Points(packetGeometry,new THREE.PointsMaterial({color:'#b4f9f0',size:.07,transparent:true,opacity:0,depthWrite:false}));scene.add(packet);
const label=document.getElementById('planet-label'),modeLabel=document.getElementById('environment-summary');
try {
  renderer=new THREE.WebGLRenderer({alpha:true,antialias:false,powerPreference:'high-performance',preserveDrawingBuffer:false});
  renderer.setClearColor('#03060b',0);renderer.outputColorSpace=THREE.SRGBColorSpace;
  document.body.appendChild(renderer.domElement);
  solar=new SolarSystem(scene);
  solar.invalidate=()=>{if(state.visible&&!document.hidden)render(0);};
  new THREE.TextureLoader().load('./assets/deep-space.png',texture=>{
    if(disposed){texture.dispose();return;}
    texture.colorSpace=THREE.SRGBColorSpace;textures.push(texture);
    backdrop=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:texture,color:'#86949e',depthWrite:false}));
    backdrop.position.z=-120;backdrop.renderOrder=-1;backdrop.userData.aspect=texture.image.width/texture.image.height;
    scene.add(backdrop);document.body.dataset.asset='ready';resize();
  },undefined,()=>{document.body.dataset.asset='fallback';if(state.visible&&!document.hidden)render(0);});
  renderer.domElement.addEventListener('webglcontextlost',event=>{
    event.preventDefault();cancelAnimationFrame(timer);timer=null;document.body.dataset.error='context-lost';
  });
  renderer.domElement.addEventListener('webglcontextrestored',()=>location.reload());
} catch(error){document.body.dataset.error='webgl';}

const forgeTransition=installForgeTransition({scene,camera,renderer,getState:()=>state});
function resize() {
  if(!renderer||disposed||innerWidth<1||innerHeight<1)return;
  const ratio=Math.min(devicePixelRatio,innerWidth>=2560?1:1.25)*quality;
  if(renderRatio!==ratio){renderer.setPixelRatio(ratio);renderRatio=ratio;}
  material.uniforms.pixelRatio.value=ratio;
  if(renderWidth!==innerWidth||renderHeight!==innerHeight){renderer.setSize(innerWidth,innerHeight);renderWidth=innerWidth;renderHeight=innerHeight;}
  camera.aspect=innerWidth/Math.max(1,innerHeight);camera.updateProjectionMatrix();
  if(backdrop) {
    const height=2*150*Math.tan(THREE.MathUtils.degToRad(camera.fov*.5));
    const cover=Math.max(height,height*camera.aspect/backdrop.userData.aspect)*1.04;
    backdrop.scale.set(cover*backdrop.userData.aspect,cover,1);
  }
  if(state.visible&&!document.hidden)render(0);
}
function monitor(now,active) {
  if(!sampleTime){sampleTime=now;return;}
  frameSamples++;
  if(now-sampleTime<1800)return;
  fps=frameSamples*1000/(now-sampleTime);sampleTime=now;frameSamples=0;
  if(fps<(active?28:12)) {fastSince=0;slowSince ||= now;if(now-slowSince>6000&&quality===1){quality=.75;slowSince=0;resize();}}
  else if(fps>(active?50:18)) {slowSince=0;fastSince ||= now;if(now-fastSince>20000&&quality<1){quality=1;fastSince=0;resize();}}
  else {slowSince=fastSince=0;}
}
function render(dt) {
  if(!renderer||disposed||innerWidth<1||innerHeight<1)return;
  const context=renderer.getContext();
  if(!context.drawingBufferWidth || !context.drawingBufferHeight)return;
  if(forgeTransition.active)return;
  const reduced=state.motion==='reduced',rig=rigTarget(state);
  const pose=observatoryCamera(state,window.ultronCameraState,camera.aspect);
  camera.position.fromArray(pose.position);camera.lookAt(...pose.target);camera.updateMatrixWorld();
  if(!reduced)time+=dt;
  stars.rotation.y=Math.sin(time*.009)*.007;
  material.uniforms.time.value=time;
  ambient=reduced?rig.ambient:THREE.MathUtils.damp(ambient,rig.ambient,4,dt);
  gridVisibility=reduced?rig.grid:THREE.MathUtils.damp(gridVisibility,rig.grid,4,dt);
  material.uniforms.visibility.value=ambient;
  if(backdrop)backdrop.material.color.setScalar(.25+ambient*.56);
  grid.material.opacity=gridVisibility;
  grid.visible=false;
  network.material.opacity=0;
  network.visible=false;
  const age=(Date.now()-(state.cue?.at||0))/1000;
  const pulse=state.cue?.kind!=='settle'&&age>=0&&age<.85 ? Math.sin(age/.85*Math.PI)*.15 : 0;
  signal.material.color.set(state.cue?.kind==='warning'?'#ff525e':'#67d6e4');
  signal.material.opacity=pulse+(['listening','speaking'].includes(state.phase)?clamp(state.level)*.08:0);
  signal.visible=signal.material.opacity>0;
  const anchor=state.anchor||{x:.5,y:.5};
  const h=2*14*Math.tan(THREE.MathUtils.degToRad(camera.fov*.5));
  signal.position.x=(anchor.x-.5)*h*camera.aspect;signal.position.y=(.5-anchor.y)*h;
  signal.scale.setScalar(reduced?1:1+clamp(age)*.6);
  const media=state.media,mediaAge=media?(Date.now()-media.at):Infinity;
  music.visible=Boolean(media&&media.duration>0&&mediaAge<30000&&state.mode!=='focus');
  if(music.visible) {
    const progress=clamp((media.progress+(media.playing?Math.max(0,mediaAge):0))/media.duration);
    music.position.set(signal.position.x,signal.position.y,0);
    music.material.opacity=media.playing?.26:.12;
    if(media.playing&&!reduced)music.rotation.z+=dt*.09;
    music.rotation.x=media.playing&&!reduced?.18:0;
    musicGeometry.setDrawRange(0,Math.max(2,Math.round(progress*161)));
  }
  const running=state.operation==='running'&&state.target&&state.mode!=='focus';
  flow.material.opacity=running?.11:0;packet.material.opacity=running&&!reduced?.55:0;
  flow.visible=Boolean(running);packet.visible=Boolean(running&&!reduced);
  if(running) {
    const start=[signal.position.x,signal.position.y,-11],target=[(state.target.x-.5)*h*camera.aspect,(.5-state.target.y)*h,-11];
    const attribute=flowGeometry.attributes.position;
    attribute.setXYZ(0,...start);attribute.setXYZ(1,...target);attribute.needsUpdate=true;
    const p=(time*.35)%1;
    packetGeometry.attributes.position.setXYZ(0,...start.map((v,i)=>v+(target[i]-v)*p));packetGeometry.attributes.position.needsUpdate=true;
    flowGeometry.computeBoundingSphere();packetGeometry.computeBoundingSphere();
  }
  solar?.step(dt,state,camera);
  stars.visible=true;technical.visible=true;
  if(solar)solar.root.visible=solar.root.visible&&!window.ultronActive;
  scene.updateMatrixWorld(true);
  renderer.render(scene,camera);frames++;
  const p=solar?.label;
  if(label) {
    label.hidden=!p?.visible;
    if(p?.visible) {
      if(label.dataset.planet!==p.id)fillPlanetFacts(label,p.id);
      const x=clamp(Math.round(p.x*innerWidth),16,Math.max(16,innerWidth-label.offsetWidth-16));
      const y=clamp(Math.round((p.y+.13)*innerHeight),90,Math.max(90,innerHeight-label.offsetHeight-16));
      label.style.transform=`translate(${x}px,${y}px)`;
    }
  }
  if(modeLabel)modeLabel.textContent=state.mode==='exploration' ? 'Exploração do sistema solar. Representação artística, sem escala astronômica.' : '';
  const assetsSettled=Boolean(document.body.dataset.asset)&&solar?.pendingMaps===0;
  const ultronSettled=Boolean(window.ultronDiagnostics?.().frames>0);
  if(state.staging&&document.body.dataset.ultronError)document.body.dataset.error='ultron-unavailable';
  if(assetsSettled&&ultronSettled&&!document.body.dataset.error)document.body.dataset.ready='true';
  document.body.dataset.frames=String(frames);
  document.body.dataset.mode=state.mode;document.body.dataset.phase=state.phase;
  document.body.dataset.travel=String(rig.distance.toFixed(3));
}
function tick(now=performance.now(),force=false) {
  cancelAnimationFrame(timer);timer=null;
  if(!renderer||disposed||!state.visible||document.hidden)return;
  const travelling=(!state.staging&&rigTarget(state).distance>.001)||observatoryCamera(state,window.ultronCameraState,camera.aspect).moving;
  const delay=frameBudget(state,travelling);
  if(!force&&!travelling&&delay&&last&&now-last<delay-1){timer=requestAnimationFrame(tick);return;}
  const dt=last?Math.min(.1,(now-last)/1000):0;last=now;
  render(dt);
  monitor(now,travelling||frameBudget(state,travelling)===16);
  if(delay)timer=requestAnimationFrame(tick);else last=0;
}
window.updateCore=value=>{
  const previous=state;state={...state,...value};
  window.ultronHost?.(state);
  if(!state.visible){cancelAnimationFrame(timer);timer=null;last=0;return;}
  if(state.motion==='reduced'||!previous.visible||previous.motion!==state.motion){last=0;tick();}
  else if(!timer)tick();
};
window.spaceDiagnostics=()=>({frames,stars:positions.length/3,mode:state.mode,phase:state.phase,
  planet:state.planet||null,travel:rigTarget(state).distance,camera:{x:camera.position.x,y:camera.position.y,z:camera.position.z},
  drawCalls:renderer?.info.render.calls||0,geometries:renderer?.info.memory.geometries||0,
  textures:renderer?.info.memory.textures||0,lights:2,fps:Number(fps.toFixed(1)),quality,
  orbitTime:solar?.elapsed||0,visible:state.visible,motion:state.motion,scheduled:Boolean(timer),
  surfaceMaps:solar?.maps||{}, solarVisibility:solar?.visibility||0, gridOpacity:grid.material.opacity,networkOpacity:network.material.opacity,
  staging:Boolean(state.staging),pendingMaps:solar?.pendingMaps,solarVisible:solar?.root.visible,
  scheduler:'animation-frame',
  budget:{drawCalls:32,lights:2},
  planets:solar?[...solar.nodes.keys()]:[]});
addEventListener('resize',resize);
addEventListener('ultron-ready',()=>{if(state.visible&&!document.hidden)render(0);});
addEventListener('ultron-camera',()=>{if(state.visible&&!document.hidden)tick();});
document.addEventListener('visibilitychange',()=>{cancelAnimationFrame(timer);timer=null;last=0;if(!document.hidden)tick();});
addEventListener('pagehide',()=>{
  disposed=true;cancelAnimationFrame(timer);solar?.dispose(scene);
  const geometries=new Set(),materials=new Set();scene.traverse(node=>{if(node.geometry)geometries.add(node.geometry);if(node.material)materials.add(node.material);});
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());renderer?.dispose();
});
resize();tick();
