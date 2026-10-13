import * as THREE from 'three';

export const PLANET_DATA=[
  ['mercury','Mercúrio',.13,1.0,'#a29282'],['venus','Vênus',.23,1.55,'#d5af74'],
  ['earth','Terra',.26,2.12,'#5cb7e2'],['mars','Marte',.19,2.65,'#df795a'],
  ['jupiter','Júpiter',.58,3.65,'#e3b693'],['saturn','Saturno',.46,4.9,'#e0ce9a'],
  ['uranus','Urano',.32,6.1,'#89d6d9'],['neptune','Netuno',.31,7.05,'#5389e0']
];
function planetTexture(kind,color) {
  const canvas=document.createElement('canvas');canvas.width=256;canvas.height=128;
  const ctx=canvas.getContext('2d'),image=ctx.createImageData(256,128),base=new THREE.Color(color);
  const noise=(x,y)=>Math.sin(x*19.13+y*43.71)*Math.sin(x*7.33-y*13.27);
  for(let y=0;y<128;y++)for(let x=0;x<256;x++) {
    const u=x/256*Math.PI*2,v=y/128*Math.PI;
    const n=Math.sin(u*3+Math.cos(v*7))*Math.sin(v*6+Math.cos(u*5))+.32*noise(u,v);
    let c=base.clone().multiplyScalar(.8+.2*n);
    if(kind==='earth') {
      c.set(n>.22 ? '#398369' : '#174d83');
      if(Math.abs(Math.cos(v))>.92)c.set('#cee8ec');
      const clouds=Math.sin(u*12+v*7)*Math.sin(v*22+u*4);
      if(clouds>.65)c.lerp(new THREE.Color('#e5eff2'),.65);
    } else if(kind==='jupiter'||kind==='saturn') {
      const band=Math.sin(v*42+.3*Math.sin(u*3));
      c.lerp(new THREE.Color('#78533d'),Math.max(0,band)*.38);
      c.lerp(new THREE.Color('#faf0dc'),Math.max(0,-band)*.28);
    } else if(kind==='mars'||kind==='mercury'||kind==='moon') {
      c.multiplyScalar(.85+.18*Math.sin(u*26+v*35)*Math.sin(v*18-u*11));
    } else if(kind==='sun') {
      c.lerp(new THREE.Color('#ff652d'),.3+.24*n);
      c.lerp(new THREE.Color('#fff2ad'),Math.max(0,noise(u*4,v*4))*.34);
    }
    const i=(y*256+x)*4;
    image.data[i]=Math.min(255,c.r*255);image.data[i+1]=Math.min(255,c.g*255);image.data[i+2]=Math.min(255,c.b*255);image.data[i+3]=255;
  }
  ctx.putImageData(image,0,0);const texture=new THREE.CanvasTexture(canvas);
  texture.colorSpace=THREE.SRGBColorSpace;return texture;
}
function orbit(radius,color,opacity=.2) {
  const points=Array.from({length:129},(_,i)=>new THREE.Vector3(Math.cos(i/128*Math.PI*2)*radius,0,Math.sin(i/128*Math.PI*2)*radius));
  return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color,transparent:true,opacity,depthWrite:false}));
}
export class SolarSystem {
  constructor(scene) {
    this.root=new THREE.Group();scene.add(this.root);
    this.root.position.set(9,4,-32);this.root.rotation.set(.46,0,.18);
    this.nodes=new Map();this.textures=[];this.elapsed=0;this.mix=0;this.visibility=1;this.disposed=false;this.maps={};
    this.sphere=new THREE.SphereGeometry(1,28,20);
    const sunTexture=planetTexture('sun','#ffc27a');this.textures.push(sunTexture);
    this.sun=new THREE.Mesh(this.sphere,new THREE.MeshStandardMaterial({map:sunTexture,emissiveMap:sunTexture,emissive:'#ffd798',emissiveIntensity:.8,roughness:1}));
    this.sun.scale.setScalar(.62);this.root.add(this.sun);this.nodes.set('sun',{mesh:this.sun,radius:.62,angle:0,orbitRadius:0});
    const glowCanvas=document.createElement('canvas');glowCanvas.width=128;glowCanvas.height=128;
    const ctx=glowCanvas.getContext('2d'),g=ctx.createRadialGradient(64,64,0,64,64,64);
    g.addColorStop(0,'rgba(255,206,135,.6)');g.addColorStop(.28,'rgba(255,140,70,.23)');g.addColorStop(1,'rgba(255,115,65,0)');
    ctx.fillStyle=g;ctx.fillRect(0,0,128,128);const glowTexture=new THREE.CanvasTexture(glowCanvas);this.textures.push(glowTexture);
    this.corona=new THREE.Sprite(new THREE.SpriteMaterial({map:glowTexture,transparent:true,opacity:.5,depthWrite:false,blending:THREE.AdditiveBlending}));
    this.corona.scale.set(3.8,3.8,1);this.root.add(this.corona);
    PLANET_DATA.forEach(([id,label,radius,orbitRadius,color],index)=>{
      const texture=planetTexture(id,color);this.textures.push(texture);
      const material=new THREE.MeshStandardMaterial({map:texture,roughness:1,metalness:0,emissive:color,emissiveIntensity:.045});
      const mesh=new THREE.Mesh(this.sphere,material);mesh.scale.setScalar(radius);
      const path=orbit(orbitRadius,'#76c8d4',.18);this.root.add(path,mesh);
      this.nodes.set(id,{mesh,label,radius,orbitRadius,angle:index*2.399+.7,path,index});
      if(id==='saturn') {
        const ringCanvas=document.createElement('canvas');ringCanvas.width=256;ringCanvas.height=1;
        const ringContext=ringCanvas.getContext('2d');
        for(let x=0;x<256;x++) {
          const tone=Math.round(155+40*Math.sin(x*.11)+20*Math.sin(x*.83));
          const alpha=(x>135&&x<147)?.12:.55+.22*Math.sin(x*.7);
          ringContext.fillStyle=`rgba(${tone+30},${tone+15},${tone},${alpha})`;ringContext.fillRect(x,0,1,1);
        }
        const ringTexture=new THREE.CanvasTexture(ringCanvas);ringTexture.colorSpace=THREE.SRGBColorSpace;this.textures.push(ringTexture);
        const ringGeometry=new THREE.RingGeometry(1.3,2.3,80);
        for(let i=0;i<ringGeometry.attributes.position.count;i++) {
          const p=new THREE.Vector3().fromBufferAttribute(ringGeometry.attributes.position,i);
          ringGeometry.attributes.uv.setXY(i,(p.length()-1.3),.5);
        }
        const ring=new THREE.Mesh(ringGeometry,new THREE.MeshStandardMaterial({map:ringTexture,side:THREE.DoubleSide,transparent:true,opacity:.8,roughness:1,depthWrite:false}));
        ring.rotation.x=Math.PI/2-.18;mesh.add(ring);
      }
    });
    const moonTexture=planetTexture('moon','#acb3b9');this.textures.push(moonTexture);
    const moon=new THREE.Mesh(this.sphere,new THREE.MeshStandardMaterial({map:moonTexture,roughness:1}));moon.scale.setScalar(.07);this.root.add(moon);
    this.nodes.set('moon',{mesh:moon,label:'Lua',radius:.07,orbitRadius:2.12,angle:0});
    for(const id of ['earth','moon']) {
      new THREE.TextureLoader().load(`./assets/${id}-nasa.jpg`,photo=>{
        if(this.disposed){photo.dispose();return;}
        // Decode the local source once; GPU surfaces are capped at 1024x512.
        const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512;
        canvas.getContext('2d').drawImage(photo.image,0,0,1024,512);photo.dispose();
        const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
        const material=this.nodes.get(id).mesh.material,old=material.map;
        material.map=texture;this.textures=this.textures.filter(t=>t!==old);this.textures.push(texture);
        old.dispose();this.maps[id]='NASA';this.invalidate?.();
      },undefined,()=>{this.maps[id]='procedural';this.invalidate?.();});
    }
    this.halo=orbit(1,'#72e3ed',.55);this.root.add(this.halo);this.halo.visible=false;
    this.key=new THREE.DirectionalLight('#fff1d8',2.3);this.key.position.set(-10,9,12);
    this.fill=new THREE.AmbientLight('#87bed9',.65);scene.add(this.key,this.fill);
    this.focused=null;this.label={visible:false};
  }
  step(dt,state,camera) {
    const reduced=state.motion==='reduced';
    if(!reduced)this.elapsed+=dt*(state.phase==='thinking'?1.15:state.phase==='executing'?1.08:1);
    const desired=state.mode==='exploration' ? 1 : 0;
    this.mix=reduced?desired:THREE.MathUtils.damp(this.mix,desired,3,dt);
    // Wide foreground content keeps the solar miniature in the far upper right.
    const isPortrait=camera.aspect<1;
    const side=isPortrait?2.2:9;
    this.root.position.lerp(new THREE.Vector3(side*(1-this.mix),4*(1-this.mix),-32+18*this.mix),reduced?1:Math.min(1,dt*3));
    this.root.scale.setScalar(isPortrait?.65:1);
    const visibility=['focus','analysis','execution'].includes(state.mode)?0:state.mode==='exploration'?1:.45;
    this.visibility=reduced?visibility:THREE.MathUtils.damp(this.visibility,visibility,5,dt);
    this.nodes.forEach((node,id)=>{
      if(id==='sun'||id==='moon')return;
      const angle=node.angle+this.elapsed*.018/(1+node.index*.35);
      const natural=new THREE.Vector3(Math.cos(angle)*node.orbitRadius,0,Math.sin(angle)*node.orbitRadius);
      const selected=state.planet===id&&state.mode==='exploration';
      const target=selected?new THREE.Vector3(-4,1.8,3):natural;
      node.mesh.position.lerp(target,reduced?1:Math.min(1,dt*3));
      const size=node.radius+(selected?1.25-node.radius:0);
      const scale=THREE.MathUtils.damp(node.mesh.scale.x,size,3,reduced?1:dt);node.mesh.scale.setScalar(scale);
      if(!reduced)node.mesh.rotation.y=this.elapsed*(id==='earth'?.025:.012);
      node.path.material.opacity=((state.mode==='focus'?.035:.12)+this.mix*.14)*this.visibility;
      node.mesh.visible=!(isPortrait&&state.mode!=='exploration'&&node.index>4);
      node.mesh.material.transparent=true;node.mesh.material.opacity=this.visibility;
      node.mesh.children.forEach(child=>{if(child.material)child.material.opacity=.8*this.visibility;});
    });
    const earth=this.nodes.get('earth').mesh,moon=this.nodes.get('moon').mesh;
    const moonDistance=Math.max(.48,earth.scale.x*1.65);
    moon.position.copy(earth.position).add(new THREE.Vector3(Math.cos(this.elapsed*.028)*moonDistance,.05,Math.sin(this.elapsed*.028)*moonDistance));
    if(state.planet==='moon'&&state.mode==='exploration'){moon.position.set(-4,1.8,3);moon.scale.setScalar(1.1);}else moon.scale.setScalar(.07);
    this.sun.position.lerp(new THREE.Vector3(state.planet==='sun'?-4:0,state.planet==='sun'?1.8:0,state.planet==='sun'?3:0),reduced?1:Math.min(1,dt*3));
    const sunSize=state.planet==='sun'?1.25:.62;
    this.sun.scale.setScalar(reduced?sunSize:THREE.MathUtils.damp(this.sun.scale.x,sunSize,3,dt));
    this.corona.scale.setScalar(state.planet==='sun'?5.2:3.8);
    this.corona.position.copy(this.sun.position);
    const selected=this.nodes.get(state.planet);
    this.halo.visible=Boolean(selected&&state.mode==='exploration');
    if(this.halo.visible) {
      this.halo.position.copy(selected.mesh.position);this.halo.position.y-=selected.mesh.scale.x*.95;
      this.halo.scale.setScalar(selected.mesh.scale.x*1.5);this.halo.rotation.y=this.elapsed*.04;
    }
    this.root.visible=this.visibility>.01;
    this.sun.material.transparent=true;this.sun.material.opacity=this.visibility;
    moon.material.transparent=true;moon.material.opacity=this.visibility;
    this.corona.material.opacity=(.4+(state.phase==='speaking'?Math.min(.15,state.level*.12):0))*this.visibility;
    this.label={visible:false};
    if(selected&&state.mode==='exploration') {
      const p=selected.mesh.getWorldPosition(new THREE.Vector3());p.project(camera);
      this.label={visible:p.z>-1&&p.z<1,x:(p.x*.5+.5),y:(-.5*p.y+.5),name:selected.label||'Sol',id:state.planet};
    }
  }
  dispose(scene) {
    this.disposed=true;
    const geometries=new Set(),materials=new Set();this.root.traverse(n=>{if(n.geometry)geometries.add(n.geometry);if(n.material)materials.add(n.material);});
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());this.textures.forEach(t=>t.dispose());
    scene.remove(this.root,this.key,this.fill);
  }
}
