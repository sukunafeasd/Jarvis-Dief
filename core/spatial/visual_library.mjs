import * as THREE from 'three';
const scene=new THREE.Scene();
const camera=new THREE.OrthographicCamera(-1,1,1,-1,.1,2000);camera.position.z=500;
scene.add(new THREE.AmbientLight('#e0f5ff',1.1));
const light=new THREE.DirectionalLight('#fff5ed',2.4);light.position.set(-100,220,350);scene.add(light);
const shapes={
 orb:new THREE.SphereGeometry(.24,20,14),node:new THREE.IcosahedronGeometry(.12,1),
 ring:new THREE.TorusGeometry(.62,.027,6,48),arc:new THREE.TorusGeometry(.57,.038,6,32,Math.PI*1.4),
 plane:new THREE.BoxGeometry(.65,.47,.06),column:new THREE.BoxGeometry(.14,.65,.12),
 marker:new THREE.ConeGeometry(.11,.3,10),connection:new THREE.CylinderGeometry(.012,.012,1,5),
 beam:new THREE.CylinderGeometry(.018,.018,.8,5),trail:new THREE.TorusGeometry(.47,.015,4,24,Math.PI*.6),
 grid:new THREE.BoxGeometry(.78,.018,.58),points:new THREE.IcosahedronGeometry(.045,0),
 segment:new THREE.TorusGeometry(.64,.027,5,14,Math.PI*.26),
 shield:new THREE.OctahedronGeometry(.47,0),spark:new THREE.OctahedronGeometry(.35,0),
 cloud:new THREE.SphereGeometry(.23,12,8),drop:new THREE.BoxGeometry(.018,.12,.016),
};
const materials=new Map();const nodes=new Map();let state={visible:true,reduced:false,elements:[]};
const sustainedMotion=new Set(['orbitar','respirar','pulsar','onda','sinalizar','chuva','neve','fluxo']);
let renderer,timer,last=0,elapsed=0,frames=0,disposed=false;
function material(color,solid=false,wire=false){
 const key=color+':'+solid+':'+wire;if(materials.has(key))return materials.get(key);
 if(materials.size>=48)return materials.values().next().value;
 const value=new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:.28,roughness:.25,metalness:.22,
  transparent:!solid,opacity:solid?1:.8,depthWrite:solid,wireframe:wire});
 value.onBeforeCompile=shader=>{
  shader.fragmentShader=shader.fragmentShader.replace('#include <dithering_fragment>',
   'gl_FragColor.rgb += diffuse * pow(clamp(1.0-abs(dot(normal,normalize(vViewPosition))),0.0,1.0),3.0)*.18;\n#include <dithering_fragment>');
 };
 value.customProgramCacheKey=()=> 'library-holographic-edge-v1';
 materials.set(key,value);return value;
}
function mesh(root,primitive,color,x=0,y=0,z=0,scale=1){
 const geometry=shapes[primitive];if(!geometry)return;
 const item=new THREE.Mesh(geometry,material(color,root.userData.solid,root.userData.wire));item.position.set(x,y,z);item.scale.setScalar(scale);
 item.userData.primitive=primitive;
 root.add(item);return item;
}
function link(root,color,a,b){
 const first=new THREE.Vector3(...a),second=new THREE.Vector3(...b),middle=first.clone().add(second).multiplyScalar(.5);
 const item=mesh(root,'connection',color,...middle.toArray());item.scale.y=first.distanceTo(second);
 item.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),second.sub(first).normalize());
}
const families={
 network(root,a,b,seed){
  const count=3+seed%3;const positions=[];mesh(root,'orb',b,0,0,0,.72);
  for(let index=0;index<count;index++){
   const angle=index*Math.PI*2/count;const position=[Math.cos(angle)*.6,Math.sin(angle)*.48,Math.sin(angle)*.17];
   positions.push(position);mesh(root,'node',a,...position);link(root,b,[0,0,0],position);
  }
 },
 slabs(root,a,b,seed){
  for(let index=0;index<3;index++){const item=mesh(root,'plane',index===2?a:b,(index-1)*.15,(index-1)*.12,(index-1)*.2);item.rotation.y=.3;item.rotation.x=-.12;}
  mesh(root,'marker',a,.44,-.37,.4,.65);
 },
 columns(root,a,b,seed){for(let index=0;index<3;index++){const item=mesh(root,'column',index===seed%3?a:b,(index-1)*.3,-.06,0);item.scale.y=.45+index*.28;}mesh(root,'grid',b,0,-.42,-.1);},
 clock(root,a,b,seed){mesh(root,'ring',a);mesh(root,'orb',b,0,0,.06,.3);link(root,b,[0,0,.1],[.36,.24,.1]);link(root,a,[0,0,.1],[-.12,.43,.1]);mesh(root,'node',b,.62,0,0,.6);},
 route(root,a,b,seed){const points=[[-.62,-.25,0],[0,.24,.08],[.61,-.1,.18]];points.forEach((p,i)=>mesh(root,i===2?'marker':'node',i===2?a:b,...p));link(root,a,points[0],points[1]);link(root,b,points[1],points[2]);},
 message(root,a,b,seed){const plane=mesh(root,'plane',a,0,.1,.06,1.2);plane.rotation.y=.18;link(root,b,[-.38,.37,.16],[0,0,.16]);link(root,b,[0,0,.16],[.38,.37,.16]);mesh(root,'node',b,.39,-.32,.22,.65);},
 weather(root,a,b,seed){
  if(seed===1){mesh(root,'orb',b,0,.04,0,1.5);const corona=mesh(root,'ring',a);corona.scale.setScalar(.82);return;}
  for(let i=0;i<4;i++)mesh(root,'cloud',a,(i-1.5)*.19,.14+(i%2)*.11,(i%2)*.16,1+(i%2)*.2);
  const rain=seed===3||seed===5||seed===6;
  if(rain)for(let i=0;i<10;i++){const item=mesh(root,seed===5?'points':'drop',b,(i%5-2)*.19,-.25-(i%2)*.23,(i%3-1)*.12);item.userData.rain=i;}
  else{const arc=mesh(root,'arc',b,0,-.1,-.15);arc.rotation.z=.6;}
 },
 orbit(root,a,b,seed){mesh(root,'orb',a,0,0,0,1.5);for(let i=0;i<2;i++){const ring=mesh(root,'ring',b);ring.rotation.x=.6+i*.6;ring.rotation.y=.3;ring.scale.setScalar(1+i*.25);}mesh(root,'node',b,.7,0,.1,.65);},
 spark(root,a,b,seed){const center=mesh(root,'spark',a,0,0,0,1.1);center.rotation.z=Math.PI/4;for(let i=0;i<4;i++)mesh(root,'points',b,Math.cos(i*Math.PI/2)*.63,Math.sin(i*Math.PI/2)*.63,.08);},
 circuit(root,a,b,seed){const center=mesh(root,'plane',a,0,0,0,.72);center.rotation.y=.23;for(let i=0;i<4;i++){const angle=i*Math.PI/2;const p=[Math.cos(angle)*.62,Math.sin(angle)*.48,0];mesh(root,'node',b,...p,.6);link(root,b,[0,0,.08],p);}},
 shield(root,a,b,seed){const item=mesh(root,'shield',a);item.scale.y=1.2;link(root,b,[-.22,0,.37],[-.02,-.18,.37]);link(root,b,[-.02,-.18,.37],[.26,.25,.37]);},
 ring(root,a,b,seed){mesh(root,'arc',a).rotation.z=seed*.35;mesh(root,'orb',b,0,0,0,.7);mesh(root,'node',b,.58,-.2,0,.6);},
 grid(root,a,b,seed){for(let i=0;i<6;i++){const tile=mesh(root,'plane',i===seed%6?a:b,(i%3-1)*.35,(Math.floor(i/3)-.5)*.39,0,.4);tile.rotation.y=.2;}},
};
function construct(item){
 const root=new THREE.Group();root.userData={solid:item.recipe?.variant==='solido',wire:item.recipe?.variant==='contorno'};
 const colors=item.colors||['#96cfe8','#ded3a9'];const [a,b]=colors;
 if(item.recipe){const recipe=item.recipe;(families[recipe.family]||families.ring)(root,a,b,recipe.seed||0);
  if(recipe.variant==='orbital'){const ring=mesh(root,'ring',b,0,0,-.2,1.35);ring.rotation.x=.8;}
  if(recipe.variant==='camadas')mesh(root,'arc',b,0,0,-.35,1.3);
  if(recipe.variant==='conectado'){mesh(root,'node',b,-.76,0,0,.5);link(root,b,[-.76,0,0],[0,0,0]);}
  if(recipe.variant==='particulas')for(let i=0;i<8;i++)mesh(root,'points',b,Math.cos(i*Math.PI/4)*.8,Math.sin(i*Math.PI/4)*.6,(i%3-1)*.1);
  if(recipe.variant==='segmentado')for(let i=0;i<6;i++){const arc=mesh(root,'segment',b,0,0,-.1,1.2);arc.rotation.z=i*Math.PI/3;}
  if(recipe.variant==='sinal')mesh(root,'marker',b,0,.8,0,.6);
 }
 const slots={centro:[0,0,.1],acima:[0,.62,0],abaixo:[0,-.62,0],esquerda:[-.62,0,0],direita:[.62,0,0],orbita:[0,0,-.18]};
 for(const part of (item.parts||[]).slice(0,6))mesh(root,part.primitive,b,...(slots[part.slot]||slots.centro));
 if(['chuva','neve','fluxo'].includes(item.animation))for(let i=0;i<6;i++){
  const particle=mesh(root,item.animation==='chuva'?'drop':'points',b,(i%3-1)*.25,-.3,i*.04);
  particle.userData.packet=i;
 }
 root.children.forEach(child=>{child.userData.basePosition=child.position.clone();child.userData.baseScale=child.scale.clone();child.userData.baseRotation=child.rotation.clone();});
 root.rotation.y=.18;root.userData.item=item;root.userData.start=elapsed;scene.add(root);return root;
}
function disposeNode(root){scene.remove(root);root.clear();}
function resize(){if(!renderer)return;renderer.setPixelRatio(Math.min(devicePixelRatio,innerWidth>=2560?1:1.25));renderer.setSize(innerWidth,innerHeight);
 camera.left=-innerWidth/2;camera.right=innerWidth/2;camera.top=innerHeight/2;camera.bottom=-innerHeight/2;camera.updateProjectionMatrix();render();}
function render(){if(!renderer||disposed)return;renderer.render(scene,camera);document.body.dataset.frames=String(++frames);}
function animate(){
 for(const root of nodes.values()){
  const item=root.userData.item;const bounds=item.bounds;if(!bounds){root.visible=false;continue;}
  root.visible=Boolean(item.visible&&item.revealed!==false);if(!root.visible)continue;
  const still=state.reduced||item.animation==='silencio';
  const age=Math.max(0,elapsed-root.userData.start);const assemble=still?1:Math.min(1,age/.65);
  const entry={condensar:.85,expandir:.2,recolher:1.3,projetar:.45,respirar:.9,estabilizar:.98};
  const easing=1-Math.pow(1-assemble,3);
  const expansion=item.animation in entry?entry[item.animation]+(1-entry[item.animation])*easing:easing;
  const scale=(36*item.scale)*expansion;root.scale.setScalar(scale*(item.focused?1.08:1));
  root.position.set(bounds.x+bounds.width/2-innerWidth/2,innerHeight/2-bounds.y-44,0);
  const active=age<1.2||item.focused;
  root.rotation.z=0;root.rotation.y=.18;root.rotation.x=0;
  root.children.forEach((child,index)=>{
   child.position.copy(child.userData.basePosition);child.scale.copy(child.userData.baseScale);child.rotation.copy(child.userData.baseRotation);
   if(!still&&item.animation==='orbitar'&&['ring','arc','trail'].includes(child.userData.primitive)){
    child.rotation.z+=elapsed*.18*(index%2?-1:1);child.rotation.y+=.14*Math.sin(elapsed*.4+index);
   }
   if(!still&&['desenhar','conectar','segmentar','alternar'].includes(item.animation)){
    const step=Math.max(.01,Math.min(1,(assemble*1.6-index*.06)));
    child.scale.multiplyScalar(step);
   }
   if(!still&&['dissolver','revelar','acender'].includes(item.animation))child.scale.multiplyScalar(.7+.3*easing);
  });
  if(!still){
   if(item.animation==='orbitar')root.rotation.y=.18+Math.sin(elapsed*.55)*.15;
   if(item.animation==='respirar')root.scale.multiplyScalar(1+Math.sin(age*.9)*.022);
   if(item.animation==='pulsar')root.scale.multiplyScalar(1+Math.sin(age*(active?3:1.4))*.035);
   if(item.animation==='aproximar')root.position.z=(1-assemble)*-70;
   else root.position.z=0;
   if(item.animation==='onda')root.rotation.x=Math.sin(age*(active?2:.7))*.09;
   if(item.animation==='varrer'&&active)root.rotation.z=(1-assemble)*.7;
   if(item.animation==='sinalizar')root.scale.multiplyScalar(1+Math.sin(age*(active?3:1.2))*.025);
   root.traverse(mesh=>{
    if(mesh.userData.rain!==undefined){const i=mesh.userData.rain;mesh.position.y=.03-((elapsed*.38+i*.093)% .72);}
    if(mesh.userData.packet!==undefined){const i=mesh.userData.packet;
     if(item.animation==='fluxo'){mesh.position.x=-.62+((elapsed*.32+i*.12)%1.24);mesh.position.y=Math.sin(mesh.position.x*3)*.15;}
     else{mesh.position.y=.25-((elapsed*(item.animation==='neve'?.13:.4)+i*.15)% .85);}
    }
   });
  }
 }
}
function schedule(){
 clearTimeout(timer);timer=null;if(disposed||!state.visible||document.hidden||document.body.dataset.error)return;
 animate();render();
 if(state.reduced)return;
  const moving=[...nodes.values()].some(root=>root.visible&&root.userData.item.animation!=='silencio'&&(sustainedMotion.has(root.userData.item.animation)||elapsed-root.userData.start<1.2||root.userData.item.focused||root.children.some(child=>child.userData.rain!==undefined||child.userData.packet!==undefined)));
 if(!moving)return;
 timer=setTimeout(()=>{const now=performance.now();elapsed+=last?Math.min(.1,(now-last)/1000):.033;last=now;schedule();},33);
}
try{
 renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power',preserveDrawingBuffer:true});
 renderer.setClearColor('#000000',0);renderer.outputColorSpace=THREE.SRGBColorSpace;document.body.appendChild(renderer.domElement);
 renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();clearTimeout(timer);document.body.dataset.error='context-lost';});
 renderer.domElement.addEventListener('webglcontextrestored',()=>location.reload());
}catch(error){document.body.dataset.error='webgl';}
window.updateCore=value=>{
 state={...state,...value};const wanted=new Set();
 for(const item of (state.elements||[]).slice(0,12)){
  if(!item.id||!item.bounds)continue;wanted.add(item.id);
  const identity=JSON.stringify([item.recipe,item.parts,item.palette,item.animation]);let root=nodes.get(item.id);
  if(root&&root.userData.identity!==identity){disposeNode(root);nodes.delete(item.id);root=null;}
  if(!root){root=construct(item);root.userData.identity=identity;nodes.set(item.id,root);}
  if(root.userData.item.revealed===false&&item.revealed!==false)root.userData.start=elapsed;
  root.userData.item=item;
 }
 for(const [id,root] of nodes)if(!wanted.has(id)){disposeNode(root);nodes.delete(id);}
 last=0;schedule();
};
window.visualDiagnostics=()=>({frames,objects:nodes.size,drawCalls:renderer?.info.render.calls||0,
 geometries:renderer?.info.memory.geometries||0,materials:materials.size,scheduled:timer!==null,visible:state.visible});
window.disposeVisualScene=()=>{disposed=true;clearTimeout(timer);timer=null;for(const root of nodes.values())disposeNode(root);nodes.clear();
 Object.values(shapes).forEach(shape=>shape.dispose());materials.forEach(value=>value.dispose());materials.clear();renderer?.dispose();};
document.addEventListener('visibilitychange',()=>{last=0;schedule();});addEventListener('resize',resize);addEventListener('pagehide',window.disposeVisualScene);
resize();document.body.dataset.ready='true';
