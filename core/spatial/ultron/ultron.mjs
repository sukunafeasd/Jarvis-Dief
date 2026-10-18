import * as THREE from './vendor/three.module.js';
import { PlanetInterior } from './planet-interior.mjs';
import { LavaActivity } from './lava-effects.mjs';
import { createCrustRelief } from './crust-relief.mjs';
import { machinedMetal } from './machined-metal.mjs';
import { BasaltLayers } from './basalt-layers.mjs';
import {sceneDistance,observatoryCamera} from '../environment-rig.mjs';

const clamp=THREE.MathUtils.clamp;
const glowVertex=`varying vec3 vNormal;varying vec3 vView;varying vec3 vLocal;void main(){vLocal=position;vec4 mv=modelViewMatrix*vec4(position,1.);vNormal=normalize(normalMatrix*normal);vView=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}`;
const glowFragment=`uniform float power;uniform float opacity;uniform float time;uniform vec3 color;varying vec3 vNormal;varying vec3 vView;varying vec3 vLocal;void main(){float rim=pow(1.-abs(dot(normalize(vNormal),normalize(vView))),power);float corona=.72+.28*sin(vLocal.y*13.+vLocal.x*9.+sin(vLocal.z*11.+time*.25)*1.7);gl_FragColor=vec4(color*rim*1.8*corona,rim*opacity*corona);}`;

export class UltronWorld {
  constructor(canvas,options={}){
    this.embedded=Boolean(options.embedded);this.hostVisible=true;this.hostStaging=true;this.hostState={staging:true};
    this.canvas=canvas;this.motionPreference=matchMedia('(prefers-reduced-motion: reduce)');this.reduced=this.motionPreference.matches;this.motionTime=0;
    this.motionAmplitude=this.reduced?.25:1;this.onMotionChange=event=>{this.reduced=event.matches;if(this.ready){this.stop();this.animate();}};this.motionPreference.addEventListener('change',this.onMotionChange);
    this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(42,1,.1,180);
    this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:this.embedded,premultipliedAlpha:!this.embedded,powerPreference:'high-performance'});
    this.renderer.setClearColor(0x030509,this.embedded?0:1);this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    this.renderer.info.autoReset=false;
    this.renderer.toneMapping=THREE.NoToneMapping;this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
    this.root=new THREE.Group();this.scene.add(this.root);this.rings=[];this.sleeves=[];this.ringFixtures=[];this.fixtureTransform=new THREE.Object3D();
    this.open=0;this.target=0;this.elapsed=0;this.frames=0;this.warningCount=0;this.phase='idle';this.ready=false;this.wakeStarted=-10;
    this.materials=[];this.clock=new THREE.Clock();this.fps=0;this.frameWindow=0;this.frameCount=0;
    this.makeSpace();this.makeLights();this.makeRings();this.makeCore();this.makeSemanticProjection();this.makeBloom();
    if(this.embedded)this.stars.visible=false;
    this.resize=()=>this.onResize();window.addEventListener('resize',this.resize);this.onResize();
    this.onVisibility=()=>{this.clock.getDelta();if(!document.hidden&&!this.frame)this.animate();};
    document.addEventListener('visibilitychange',this.onVisibility);
    this.contextLost=e=>{e.preventDefault();this.stop();if(this.embedded){canvas.hidden=true;document.body.dataset.ultronError='context-lost';return;}document.body.classList.add('scene-unavailable');const cover=document.querySelector('#scene-loading');cover?.classList.remove('complete');if(cover)cover.lastElementChild.textContent='Cena 3D suspensa. Diagnóstico continua disponível.';};
    canvas.addEventListener('webglcontextlost',this.contextLost);
    canvas.addEventListener('webglcontextrestored',()=>location.reload());
  }
  async init(){
    const asset=await new THREE.FileLoader().setResponseType('json').loadAsync(new URL('./assets/ultron-crust.json',import.meta.url).href);
    const texture=await new THREE.TextureLoader().loadAsync(`data:${asset.mime};base64,${asset.data}`);
    texture.colorSpace=THREE.SRGBColorSpace;texture.wrapS=THREE.RepeatWrapping;texture.anisotropy=Math.min(8,this.renderer.capabilities.getMaxAnisotropy());
    const source=texture.image;const canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height;
    const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(source,0,0);const pixels=context.getImageData(0,0,canvas.width,canvas.height);
    const roughCanvas=document.createElement('canvas');roughCanvas.width=canvas.width;roughCanvas.height=canvas.height;const roughContext=roughCanvas.getContext('2d');const roughPixels=roughContext.createImageData(canvas.width,canvas.height);
    for(let i=0;i<pixels.data.length;i+=4){const r=pixels.data[i],g=pixels.data[i+1],b=pixels.data[i+2];const molten=clamp((r-Math.max(g,b)*1.3-20)/100,0,1);const rough=THREE.MathUtils.lerp(clamp(.92-(r+g+b)/1300,.57,.92),.24,molten);roughPixels.data[i]=rough*255;roughPixels.data[i+1]=rough*255;roughPixels.data[i+2]=rough*255;roughPixels.data[i+3]=255;pixels.data[i]=255*molten;pixels.data[i+1]=60*molten;pixels.data[i+2]=10*molten;}
    roughContext.putImageData(roughPixels,0,0);this.roughnessMap=new THREE.CanvasTexture(roughCanvas);this.roughnessMap.wrapS=THREE.RepeatWrapping;
    context.putImageData(pixels,0,0);this.emission=new THREE.CanvasTexture(canvas);this.emission.colorSpace=THREE.SRGBColorSpace;this.emission.wrapS=THREE.RepeatWrapping;
    const relief=createCrustRelief(source,pixels.data);this.reliefMap=relief.texture;
    this.crustMaterial=new THREE.MeshStandardMaterial({map:texture,bumpMap:this.reliefMap,bumpScale:.095,displacementMap:this.reliefMap,displacementScale:.038,displacementBias:-.015,metalness:.38,roughness:1,roughnessMap:this.roughnessMap,color:0x81858b,emissive:0xffa17e,emissiveMap:this.emission,emissiveIntensity:1.4});
    const aperture={value:0};this.aperture=aperture;this.lavaTime={value:0};
    this.crustMaterial.onBeforeCompile=shader=>{
      shader.uniforms.uAperture=aperture;
      shader.uniforms.uLavaTime=this.lavaTime;
      shader.uniforms.uEmissionTexel={value:new THREE.Vector2(1/canvas.width,1/canvas.height)};
      shader.vertexShader='varying float vUltronFacing;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvec3 ultronCenter=(modelMatrix*vec4(0.,0.,0.,1.)).xyz;vec3 ultronDirection=normalize((modelMatrix*vec4(position,0.)).xyz);vUltronFacing=dot(ultronDirection,normalize(cameraPosition-ultronCenter));');
      shader.fragmentShader='uniform float uAperture;uniform float uLavaTime;uniform vec2 uEmissionTexel;varying float vUltronFacing;\n'+shader.fragmentShader.replace('#include <clipping_planes_fragment>','#include <clipping_planes_fragment>\nif(uAperture>.02 && vUltronFacing > mix(1.,.89,uAperture)) discard;').replace('#include <emissivemap_fragment>',`#include <emissivemap_fragment>
        float heat=texture2D(emissiveMap,vEmissiveMapUv).r;
        float nearby=max(max(texture2D(emissiveMap,vEmissiveMapUv+uEmissionTexel*vec2(3.,0.)).r,texture2D(emissiveMap,vEmissiveMapUv-uEmissionTexel*vec2(3.,0.)).r),max(texture2D(emissiveMap,vEmissiveMapUv+uEmissionTexel*vec2(0.,3.)).r,texture2D(emissiveMap,vEmissiveMapUv-uEmissionTexel*vec2(0.,3.)).r));
        float bank=max(0.,nearby-heat)*(1.-smoothstep(.08,.5,heat));
        float flow=.5+.5*sin(vMapUv.x*43.982297+vMapUv.y*29.-uLavaTime*.7+sin(vMapUv.y*73.+uLavaTime*.32)*1.3);
        float hot=smoothstep(.48,.94,heat)*(.65+flow*.35);
        float crustFilm=.5+.5*sin(vMapUv.x*81.681409+vMapUv.y*89.+sin(vMapUv.y*37.-uLavaTime*.22)*2.);
        vec3 moltenColor=mix(vec3(.78,.023,.004),vec3(1.2,.62,.19),hot);
        totalEmissiveRadiance=moltenColor*heat*emissive.r*mix(.78,1.28,flow);
        totalEmissiveRadiance+=vec3(1.,.025,.002)*pow(heat,.55)*.10;
        totalEmissiveRadiance*=mix(.82,1.,smoothstep(.25,.62,crustFilm));
        totalEmissiveRadiance+=vec3(.48,.035,.004)*bank*(.75+flow*.25);
        diffuseColor.rgb*=mix(.84,1.,smoothstep(.02,.3,heat));
      `);
    };
    this.crust=new THREE.Mesh(new THREE.SphereGeometry(1.68,128,88),this.crustMaterial);this.root.add(this.crust);
    this.interior=new PlanetInterior(texture,this.emission);this.root.add(this.interior.group);
    this.lava=new LavaActivity(pixels.data,canvas.width,canvas.height,relief.pixels);this.crust.add(this.lava.group);
    this.basalt=new BasaltLayers(pixels.data,relief.pixels,canvas.width,canvas.height,this.lavaTime);this.crust.add(this.basalt.mesh);
    this.cameraFacing=new THREE.Vector3();this.localFacing=new THREE.Vector3();this.inverseRotation=new THREE.Quaternion();this.socketDirection=new THREE.Vector3();
    this.makeArmor();this.makeAtmosphere();this.ready=true;this.clock.start();this.lastRender=-1;this.animate();
    if(!this.embedded){document.body.dataset.ready='true';document.querySelector('#scene-loading')?.classList.add('complete');window.ultronDiagnostics=()=>this.diagnostics();}
  }
  makeLights(){
    this.scene.add(new THREE.AmbientLight(0x7a97b0,.36));
    const key=new THREE.DirectionalLight(0xc1d5e2,2.2);key.position.set(-4,5,6);this.scene.add(key);
    const rim=new THREE.DirectionalLight(0x6bc8d6,2.2);rim.position.set(5,1,-4);this.scene.add(rim);
    const bounce=new THREE.DirectionalLight(0xff703c,.55);bounce.position.set(-3,-3,-2);this.scene.add(bounce);
    this.coreLight=new THREE.PointLight(0xff4428,16,8,2);this.coreLight.position.set(-.5,.5,2.8);this.root.add(this.coreLight);
  }
  makeSpace(){
    let seed=91247;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
    const positions=[],colors=[];
    for(let i=0;i<2400;i++){positions.push((random()-.5)*120,(random()-.5)*85,-15-random()*70);const shade=.25+random()*.65;colors.push(shade*.85,shade*.95,shade);}
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
    this.stars=new THREE.Points(geometry,new THREE.PointsMaterial({vertexColors:true,size:.055,transparent:true,opacity:.85,sizeAttenuation:true}));this.scene.add(this.stars);
    const dust=[];for(let i=0;i<170;i++){const a=random()*Math.PI*2,r=2.6+random()*3;dust.push(Math.cos(a)*r,Math.sin(a)*r,(random()-.5)*3);}
    const particles=new THREE.BufferGeometry();particles.setAttribute('position',new THREE.Float32BufferAttribute(dust,3));
    this.dust=new THREE.Points(particles,new THREE.PointsMaterial({color:0xcb8173,size:.017,transparent:true,opacity:.32,blending:THREE.AdditiveBlending,depthWrite:false}));this.root.add(this.dust);
  }
  makeRings(){
    const metal=machinedMetal({color:0x303740,metalness:.88,roughness:.58});
    const seam=new THREE.MeshStandardMaterial({color:0x471d16,emissive:0xff3b14,emissiveIntensity:1.1,metalness:.7,roughness:.52});
    for(let ring=0;ring<3;ring++){
      const group=new THREE.Group();const radius=2.02+ring*.25;
      const segments=ring===1?6:8;
      for(let i=0;i<segments;i++){
        const arm=new THREE.Group();const angle=i*Math.PI*2/segments;
        const arc=new THREE.Mesh(new THREE.TorusGeometry(radius,.052+(ring===0?.025:0),8,32,Math.PI*2/segments-.10),metal);arc.rotation.z=angle;arm.add(arc);
        const line=new THREE.Mesh(new THREE.TorusGeometry(radius-.04,.013,5,28,Math.PI*2/segments-.13),seam);line.rotation.z=angle+.015;arm.add(line);
        const plate=new THREE.Mesh(new THREE.BoxGeometry(.09,.15,.16),metal);plate.position.set(Math.cos(angle)*radius,Math.sin(angle)*radius,0);plate.rotation.z=angle;arm.add(plate);
        group.add(arm);this.sleeves.push({object:arm,angle:angle+Math.PI/segments,ring});
      }
      group.rotation.set(ring===1?1.08:.2,ring===2?.93:.1,ring*.8);
      const fixtures=new THREE.InstancedMesh(new THREE.BoxGeometry(.044,.095,.042),metal,72);
      const dummy=new THREE.Object3D();
      for(let i=0;i<72;i++){
        const angle=i/72*Math.PI*2;
        dummy.position.set(Math.cos(angle)*(radius+.045),Math.sin(angle)*(radius+.045),.038);
        dummy.rotation.z=angle;dummy.scale.setScalar(i%3===0?1:.55);dummy.updateMatrix();fixtures.setMatrixAt(i,dummy.matrix);
      }
      group.add(fixtures);
      this.ringFixtures.push({mesh:fixtures,radius,segments,ring});
      this.root.add(group);this.rings.push(group);
    }
    const ticks=[];
    for(let i=0;i<180;i++){
      const a=i/180*Math.PI*2,r=2.63,length=i%5===0?.072:.025;
      ticks.push(Math.cos(a)*r,Math.sin(a)*r,0,Math.cos(a)*(r+length),Math.sin(a)*(r+length),0);
    }
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(ticks,3));
    this.indexRing=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:0xe14c3d,transparent:true,opacity:.32,blending:THREE.AdditiveBlending}));
    this.indexRing.rotation.x=.22;this.root.add(this.indexRing);
    this.wakePulse=new THREE.Mesh(new THREE.TorusGeometry(1,.012,4,128),new THREE.MeshBasicMaterial({color:0xff765b,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false}));this.root.add(this.wakePulse);
    this.alertMarkers=new THREE.Group();this.root.add(this.alertMarkers);
  }
  makeArmor(){
    this.armor=new THREE.Group();
    const dark=machinedMetal({color:0x19222b,roughness:.75,metalness:.9});
    const edge=new THREE.MeshStandardMaterial({color:0x411a18,emissive:0xff4023,emissiveIntensity:.9,metalness:.75,roughness:.5});
    for(let i=0;i<12;i++){
      const a=i*Math.PI*2/12;
      const socket=new THREE.Group();socket.rotation.set(.3,a,0);
      const block=new THREE.Mesh(new THREE.BoxGeometry(.14,.44,.12),dark);block.position.set(0,.08,1.72);socket.add(block);
      const slit=new THREE.Mesh(new THREE.BoxGeometry(.018,.30,.025),edge);slit.position.set(.045,.06,1.79);socket.add(slit);
      this.armor.add(socket);
    }
    this.root.add(this.armor);
  }
  makeCore(){
    this.core=new THREE.Group();this.reactorTime={value:0};
    const coreMaterial=new THREE.ShaderMaterial({uniforms:{time:this.reactorTime},
      vertexShader:`varying vec3 vLocal;varying vec3 vNormal;varying vec3 vView;void main(){vLocal=position;vec4 view=modelViewMatrix*vec4(position,1.);vNormal=normalize(normalMatrix*normal);vView=normalize(-view.xyz);gl_Position=projectionMatrix*view;}`,
      fragmentShader:`uniform float time;varying vec3 vLocal;varying vec3 vNormal;varying vec3 vView;void main(){float rim=pow(1.-abs(dot(normalize(vNormal),normalize(vView))),2.);float ribbon=pow(.5+.5*sin(vLocal.y*61.+sin(vLocal.x*49.-time*.9)*2.+time*1.3),5.);float cells=.5+.5*sin(vLocal.z*51.+cos(vLocal.y*47.+time*.6)*2.);vec3 plasma=mix(vec3(.64,.025,.006),vec3(1.7,.57,.14),ribbon*.7+cells*.3);gl_FragColor=vec4(plasma+vec3(1.,.24,.06)*rim,1.);}`});
    this.core.add(new THREE.Mesh(new THREE.SphereGeometry(.28,48,32),coreMaterial));
    const plasma=new THREE.MeshBasicMaterial({color:0xff4e16,wireframe:true,transparent:true,opacity:.5,blending:THREE.AdditiveBlending});
    this.innerPlasma=new THREE.Mesh(new THREE.IcosahedronGeometry(.39,3),plasma);this.core.add(this.innerPlasma);
    for(let i=0;i<7;i++){
      const line=new THREE.Mesh(new THREE.TorusGeometry(.48+i*.027,.008,4,72),new THREE.MeshBasicMaterial({color:i%2?0xffad68:0xff4a25,transparent:true,opacity:.58,blending:THREE.AdditiveBlending}));
      line.rotation.set(i*.51,i*.44,i*.24);this.core.add(line);
    }
    this.core.position.z=.35;this.root.add(this.core);
    this.scanRing=new THREE.Mesh(new THREE.TorusGeometry(1.77,.015,4,100),new THREE.MeshBasicMaterial({color:0xffbe8b,transparent:true,opacity:0,blending:THREE.AdditiveBlending,depthWrite:false}));this.root.add(this.scanRing);
  }
  makeSemanticProjection(){
    this.semantic=new THREE.Group();this.semantic.position.set(4.15,2.0,-.45);this.semantic.scale.setScalar(.62);this.root.add(this.semantic);this.semantic.visible=false;
    const material=new THREE.MeshStandardMaterial({color:0x274650,emissive:0x39bfc4,emissiveIntensity:.5,metalness:.8,roughness:.3});
    this.symbols={};
    const shield=new THREE.Shape();shield.moveTo(-.32,.35);shield.lineTo(.32,.35);shield.lineTo(.28,-.12);shield.quadraticCurveTo(.25,-.27,0,-.42);shield.quadraticCurveTo(-.25,-.27,-.28,-.12);shield.closePath();
    this.symbols.shield=new THREE.Mesh(new THREE.ExtrudeGeometry(shield,{depth:.1,bevelEnabled:true,bevelSize:.025,bevelThickness:.025,bevelSegments:2,steps:1}),material);
    const vault=new THREE.Group();for(let i=0;i<3;i++){const slab=new THREE.Mesh(new THREE.BoxGeometry(.62,.12,.42),material);slab.position.y=(i-1)*.19;vault.add(slab);vault.add(new THREE.LineSegments(new THREE.EdgesGeometry(slab.geometry),new THREE.LineBasicMaterial({color:0x82dbe0})));vault.children[vault.children.length-1].position.copy(slab.position);}
    this.symbols.vault=vault;
    this.symbols.diagnostic=new THREE.Mesh(new THREE.IcosahedronGeometry(.31,0),new THREE.MeshStandardMaterial({color:0x365864,emissive:0x54cad8,emissiveIntensity:.7,metalness:.8,roughness:.2,wireframe:true}));
    this.symbols.cleanup=new THREE.Mesh(new THREE.TorusKnotGeometry(.21,.025,80,6,2,3),material);
    this.symbols.simulation=new THREE.Mesh(new THREE.OctahedronGeometry(.34),material);
    for(const [name,object] of Object.entries(this.symbols)){object.visible=false;this.semantic.add(object);}
    this.semanticOrbit=new THREE.Mesh(new THREE.TorusGeometry(.55,.007,4,70),new THREE.MeshBasicMaterial({color:0x89d3d8,transparent:true,opacity:.65,blending:THREE.AdditiveBlending}));this.semanticOrbit.rotation.x=1.15;this.semantic.add(this.semanticOrbit);
  }
  setContext(name){this.currentContext=name;for(const [id,object] of Object.entries(this.symbols))object.visible=id===(this.symbols[name]?name:'shield');this.semantic.visible=this.phase!=='idle'&&!this.mobile;}
  focusObservation(severity){this.observationIntensity=severity==='critical'?1.2:severity==='warning'?.65:.2;}
  makeAtmosphere(){
    this.atmosphere=new THREE.Mesh(new THREE.SphereGeometry(1.73,64,40),new THREE.ShaderMaterial({uniforms:{power:{value:3.3},opacity:{value:.25},time:this.lavaTime,color:{value:new THREE.Color(0xf94f3b)}},vertexShader:glowVertex,fragmentShader:glowFragment,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.FrontSide}));this.root.add(this.atmosphere);
  }
  makeBloom(){
    this.renderTarget=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,depthBuffer:true});
    this.blurA=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,depthBuffer:false});this.blurB=this.blurA.clone();
    this.postScene=new THREE.Scene();this.postCamera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);
    const vertex='varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}';
    this.blurMaterial=new THREE.ShaderMaterial({uniforms:{source:{value:null},direction:{value:new THREE.Vector2()},highpass:{value:1}},vertexShader:vertex,fragmentShader:`varying vec2 vUv;uniform sampler2D source;uniform vec2 direction;uniform float highpass;vec3 sampleAt(vec2 uv){vec3 c=texture2D(source,uv).rgb;return mix(c,max(c-vec3(.72),vec3(0.)),highpass);}void main(){vec3 c=sampleAt(vUv)*.227027;c+=sampleAt(vUv+direction*1.384615)*.316216;c+=sampleAt(vUv-direction*1.384615)*.316216;c+=sampleAt(vUv+direction*3.230769)*.070270;c+=sampleAt(vUv-direction*3.230769)*.070270;gl_FragColor=vec4(c,1.);}`,depthTest:false,depthWrite:false,toneMapped:false});
    this.composite=new THREE.ShaderMaterial({uniforms:{sceneTexture:{value:this.renderTarget.texture},bloom:{value:this.blurB.texture},strength:{value:.65},embedded:{value:this.embedded?1:0}},vertexShader:vertex,fragmentShader:`varying vec2 vUv;uniform sampler2D sceneTexture;uniform sampler2D bloom;uniform float strength;uniform float embedded;void main(){vec4 source=texture2D(sceneTexture,vUv);vec3 glow=texture2D(bloom,vUv).rgb*strength;vec3 c=source.rgb+glow;c=vec3(1.)-exp(-c*1.05);c=pow(max(c,vec3(0.)),vec3(1./2.2));float alpha=mix(1.,clamp(source.a+max(max(glow.r,glow.g),glow.b),0.,1.),embedded);gl_FragColor=vec4(c,alpha);}`,depthTest:false,depthWrite:false,toneMapped:false});
    this.quad=new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.blurMaterial);this.postScene.add(this.quad);
  }
  onResize(){
    const width=innerWidth,height=innerHeight;
    if(width<1||height<1)return;
    this.mobile=width<700;
    this.renderer.setSize(width,height,false);this.camera.aspect=width/height;this.camera.fov=this.embedded?48:this.mobile?46:42;this.camera.updateProjectionMatrix();
    if(this.embedded&&!this.embeddedPlaced){
      const h=2*15*Math.tan(THREE.MathUtils.degToRad(24));
      const reference=2*(this.mobile?12.6:9.9)*Math.tan(THREE.MathUtils.degToRad(this.mobile?23:21));
      this.root.position.set(((this.mobile?.5:.16)-.5)*h*this.camera.aspect,(.5-.33)*h,-12);
      this.root.scale.setScalar(.24*h/reference);
      this.embeddedPlaced=true;
    }else if(!this.embedded)this.root.position.set(this.mobile?0:width<1100?-1.5:-1.3,this.mobile?2.35:.18,0);
    const size=this.renderer.getDrawingBufferSize(new THREE.Vector2());this.renderTarget.setSize(size.x,size.y);this.blurA.setSize(Math.ceil(size.x/2),Math.ceil(size.y/2));this.blurB.setSize(Math.ceil(size.x/2),Math.ceil(size.y/2));
    this.updateCamera();
    this.semantic.visible=this.phase!=='idle'&&!this.mobile&&!!this.currentContext;
    if(this.ready&&this.reduced&&this.hostVisible){this.stop();this.animate();}
  }
  updateCamera(){
    if(this.embedded){
      const pose=observatoryCamera(this.hostState,this.hostState.ultronFocus,this.camera.aspect);
      this.camera.position.fromArray(pose.position);this.camera.lookAt(...pose.target);
    }else{
      this.camera.position.set(Math.sin(this.motionTime*.08)*.024*this.motionAmplitude,0,(this.mobile?12.6:9.9)-this.open*(this.mobile?.2:1.1));
      this.camera.lookAt(0,0,0);
    }
    this.camera.updateMatrixWorld();
  }
  setState(phase,findings=[]){
    if(this.phase==='idle'&&phase!=='idle')this.wakeStarted=this.elapsed;
    this.phase=phase;this.target=phase==='idle'?0:1;
    this.alertMarkers.visible=phase!=='idle';
    this.semantic.visible=phase!=='idle'&&!this.mobile&&!!this.currentContext;
    const warnings=findings.filter(item=>item.severity==='warning'||item.severity==='critical');
    const signature=JSON.stringify(warnings.map(item=>[item.id,item.severity]));
    if(signature!==this.warningSignature){
      this.warningSignature=signature;
      this.warningCount=warnings.length;
      while(this.alertMarkers.children.length){const object=this.alertMarkers.children[0];object.geometry.dispose();object.material.dispose();this.alertMarkers.remove(object);}
      warnings.slice(0,8).forEach((item,index)=>{const marker=new THREE.Mesh(new THREE.OctahedronGeometry(.045),new THREE.MeshBasicMaterial({color:item.severity==='critical'?0xff473e:0xf4b35f}));const angle=index*.8+.3;marker.position.set(Math.cos(angle)*2.82,Math.sin(angle)*2.82,.1);this.alertMarkers.add(marker);});
    }
    if(this.ready&&this.reduced&&this.hostVisible){this.stop();this.animate();}
  }
  render(){
    if(innerWidth<1||innerHeight<1)return;
    const context=this.renderer.getContext();
    if(!context.drawingBufferWidth||!context.drawingBufferHeight)return;
    this.renderer.info.reset();
    this.renderer.setRenderTarget(this.renderTarget);this.renderer.render(this.scene,this.camera);
    this.quad.material=this.blurMaterial;this.blurMaterial.uniforms.source.value=this.renderTarget.texture;this.blurMaterial.uniforms.highpass.value=1;this.blurMaterial.uniforms.direction.value.set(2/this.blurA.width,0);
    this.renderer.setRenderTarget(this.blurA);this.renderer.render(this.postScene,this.postCamera);
    this.blurMaterial.uniforms.source.value=this.blurA.texture;this.blurMaterial.uniforms.highpass.value=0;this.blurMaterial.uniforms.direction.value.set(0,2/this.blurA.height);
    this.renderer.setRenderTarget(this.blurB);this.renderer.render(this.postScene,this.postCamera);
    this.quad.material=this.composite;this.renderer.setRenderTarget(null);this.renderer.render(this.postScene,this.postCamera);
  }
  animate(){
    this.frame=null;if(document.hidden||!this.hostVisible)return;
    const travelling=this.embedded&&(sceneDistance(this.hostState,Date.now(),this.reduced)>.001||observatoryCamera(this.hostState,this.hostState.ultronFocus,this.camera.aspect).moving);
    const interval=1/(this.embedded?(travelling?60:this.phase==='idle'?12:30):this.mobile||this.reduced?30:60)-.001;
    const now=this.clock.getElapsedTime();
    if(!this.reduced&&!travelling&&now-(this.lastRender||0)<interval){this.frame=requestAnimationFrame(()=>this.animate());return;}
    const delta=this.reduced?0:Math.min(this.clock.elapsedTime-(this.lastRender||0),.08);this.lastRender=this.clock.elapsedTime;this.elapsed+=delta;this.frames++;
    this.frameWindow+=delta;this.frameCount++;if(this.frameWindow>=1){this.fps=this.frameCount/this.frameWindow;this.frameWindow=0;this.frameCount=0;}
    this.open=this.reduced?this.target:THREE.MathUtils.damp(this.open,this.target,1.45,delta);
    this.updateCamera();
    const rate=this.reduced?.25:1;this.motionAmplitude=THREE.MathUtils.damp(this.motionAmplitude,rate,3,delta);const motion=this.motionAmplitude;
    this.motionTime+=delta*rate;const t=this.motionTime;
    this.crust.rotation.y=t*.14;this.crust.rotation.x=Math.sin(t*.21)*.07*motion;this.armor.rotation.copy(this.crust.rotation);
    this.aperture.value=this.open;
    this.lavaTime.value=t;
    this.reactorTime.value=t;
    this.cameraFacing.copy(this.camera.position).sub(this.root.position).normalize();
    this.interior.update(t,this.open,this.cameraFacing,motion);
    this.inverseRotation.copy(this.crust.quaternion).invert();this.localFacing.copy(this.cameraFacing).applyQuaternion(this.inverseRotation);
    this.lava.update(t,rate,this.open,this.localFacing,this.renderer.getPixelRatio());
    this.basalt.update(this.open,this.localFacing);
    for(const socket of this.armor.children){this.socketDirection.set(0,0,1).applyQuaternion(socket.quaternion).applyQuaternion(this.armor.quaternion);socket.scale.setScalar(this.socketDirection.dot(this.cameraFacing)>.81?1-this.open*.97:1);}
    this.crustMaterial.emissiveIntensity=1.35+this.open*.75+Math.sin(t*1.3)*.12*motion;
    this.atmosphere.material.uniforms.opacity.value=.22+this.open*.12;
    this.core.rotation.set(t*.38,t*.55,t*.2);this.core.scale.setScalar(1+Math.sin(t*2.1)*.1*motion);
    this.innerPlasma.rotation.y=t*-.44;
    this.coreLight.intensity=16+this.open*12+Math.sin(t*1.1)*.8*motion;
    this.rings.forEach((ring,index)=>{ring.rotation.z=t*(index%2?-.15:.11)+index*.8;ring.rotation.y=(index===2?.93:.1)+Math.sin(t*.3+index)*.12*motion;});
    this.sleeves.forEach(({object,angle,ring})=>{const extension=this.open*(.23+ring*.08);object.position.set(Math.cos(angle)*extension,Math.sin(angle)*extension,0);});
    for(const {mesh,radius,segments,ring} of this.ringFixtures){
      const extension=this.open*(.23+ring*.08);
      for(let i=0;i<72;i++){
        const angle=i/72*Math.PI*2,segmentAngle=(Math.floor(i*segments/72)+.5)*Math.PI*2/segments;
        this.fixtureTransform.position.set(Math.cos(angle)*(radius+.045)+Math.cos(segmentAngle)*extension,Math.sin(angle)*(radius+.045)+Math.sin(segmentAngle)*extension,.038);
        this.fixtureTransform.rotation.z=angle;this.fixtureTransform.scale.setScalar(i%3===0?1:.55);this.fixtureTransform.updateMatrix();mesh.setMatrixAt(i,this.fixtureTransform.matrix);
      }
      mesh.instanceMatrix.needsUpdate=true;
    }
    this.indexRing.rotation.z=t*-.07;this.indexRing.material.opacity=.26+this.open*.28;
    this.dust.rotation.z=t*-.075;this.dust.material.opacity=.32+this.open*.28;
    this.stars.rotation.z=Math.sin(t*.009)*.004*motion;
    this.scanRing.material.opacity=this.phase==='scanning'?.30:0;
    this.scanRing.position.z=this.phase==='scanning'?Math.sin(t*.7)*1.1:0;this.scanRing.rotation.x=Math.PI/2+Math.sin(t*.5)*.28*motion;
    this.alertMarkers.rotation.z=t*.012;
    this.semanticOrbit.rotation.z=t*.38;this.semanticOrbit.rotation.x=1.15+Math.sin(t*.65)*.3*motion;
    for(const object of Object.values(this.symbols)){if(object.visible){object.rotation.y=Math.sin(t*.55)*.5*motion;object.rotation.z=Math.sin(t*.35)*.06*motion;}}
    this.semantic.position.y=2+Math.sin(t*.9)*.06*motion;
    this.observationIntensity=THREE.MathUtils.damp(this.observationIntensity||0,0,1.1,delta);
    this.coreLight.intensity+=this.observationIntensity*8;
    const wakeAge=this.elapsed-this.wakeStarted;const wake=clamp(wakeAge/2.2,0,1);this.wakePulse.scale.setScalar(1.7+wake*3);this.wakePulse.material.opacity=wakeAge<2.2&&!this.reduced?(1-wake)*.45:0;
    if(this.embedded){
      this.coreLight.intensity*=this.root.scale.x*this.root.scale.x;
      this.root.visible=true;this.semantic.visible=false;this.stars.visible=false;
    }
    this.render();if(!this.reduced)this.frame=requestAnimationFrame(()=>this.animate());
  }
  host(state){
    const changed=this.hostState.motion!==state.motion||this.hostState.staging!==state.staging;
    this.hostState={...this.hostState,...state};this.hostVisible=this.hostState.visible!==false;
    this.hostStaging=Boolean(this.hostState.staging);this.reduced=this.hostState.motion==='reduced';
    if(!this.hostVisible)this.stop();
    else if(this.ready&&(changed||!this.frame)){this.stop();this.lastRender=-1;this.animate();}
  }
  diagnostics(){return {ready:this.ready,phase:this.phase,context:this.currentContext,frames:this.frames,camera:this.camera.position.toArray(),worldPosition:this.root.position.toArray(),worldScale:this.root.scale.toArray(),projectedCenter:this.root.position.clone().project(this.camera).toArray(),travel:this.embedded?sceneDistance(this.hostState,Date.now(),this.reduced):0,rotation:this.crust?.rotation.y,aperture:this.open,closedInterior:!!this.interior,throatDepth:.66,basaltTiles:this.basalt?.tiles.length,lava:this.lava?.diagnostics(),fps:Math.round(this.fps),pixelRatio:this.renderer.getPixelRatio(),textures:this.renderer.info.memory.textures,geometries:this.renderer.info.memory.geometries,drawCalls:this.renderer.info.render.calls,warningMarkers:this.warningCount,mobile:this.mobile};}
  stop(){if(this.frame)cancelAnimationFrame(this.frame);this.frame=null;}
  dispose(){this.stop();window.removeEventListener('resize',this.resize);document.removeEventListener('visibilitychange',this.onVisibility);this.motionPreference.removeEventListener('change',this.onMotionChange);this.scene.traverse(item=>{if(item.isInstancedMesh)item.dispose();item.geometry?.dispose();for(const material of Array.isArray(item.material)?item.material:[item.material]){if(!material)continue;for(const value of Object.values(material))if(value?.isTexture)value.dispose();material.dispose();}});this.renderTarget.dispose();this.blurA.dispose();this.blurB.dispose();this.blurMaterial.dispose();this.composite.dispose();this.quad.geometry.dispose();this.renderer.dispose();}
}

