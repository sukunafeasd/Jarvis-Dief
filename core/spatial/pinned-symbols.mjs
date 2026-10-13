import * as THREE from 'three';
import {profileFor} from './presentation_profiles.mjs';

// Compact previews have their own trusted silhouettes and motion vocabulary.
export function buildPinnedSymbol(model) {
  const root=new THREE.Group(),profile=profileFor(model.kind);
  root.userData.pinKind=model.kind;
  function mesh(geometry,color=profile.accent) {
    const item=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,emissive:color,
      emissiveIntensity:.45,metalness:.55,roughness:.25}));root.add(item);return item;
  }
  function ring(radius,color=profile.secondary) {
    return mesh(new THREE.TorusGeometry(radius,.016,5,48,Math.PI*1.72),color);
  }
  function slab(x,y,z,color) {
    const item=mesh(new THREE.BoxGeometry(1.05,.68,.09),color);item.position.set(x,y,z);
    item.add(new THREE.LineSegments(new THREE.EdgesGeometry(item.geometry),
      new THREE.LineBasicMaterial({color:profile.secondary,transparent:true,opacity:.8})));
    return item;
  }
  const kind=model.kind;
  if(kind==='weather') {
    const code=Number.isFinite(model.code)?model.code:-1;
    if(code>0)for(let i=0;i<3;i++) {
      const cloud=mesh(new THREE.SphereGeometry(i===1?.32:.25,16,10),'#b1d5e6');
      cloud.position.set((i-1)*.34,i===1?.18:.04,-i*.05);cloud.scale.set(1.16,.82,1);cloud.userData.pinCloud=i;
    }
    if(code>=0&&code<=2){const sun=mesh(new THREE.IcosahedronGeometry(.23,2),model.is_day===0?'#bed1ef':'#ffc259');sun.position.set(.45,.30,-.2);sun.userData.pinPulse=0;}
    if(code>=51){
      const snow=[71,73,75,77,85,86].includes(code),count=snow?20:32,positions=new Float32Array(count*(snow?3:6));
      const drops=new (snow?THREE.Points:THREE.LineSegments)(new THREE.BufferGeometry().setAttribute('position',new THREE.BufferAttribute(positions,3)),
        new (snow?THREE.PointsMaterial:THREE.LineBasicMaterial)({color:snow?'#daefff':'#52e5ff',transparent:true,opacity:.85,depthWrite:false,...(snow?{size:.04}:{})}));
      drops.userData.pinRain={snow,count};root.add(drops);
      drops.geometry.boundingSphere=new THREE.Sphere(new THREE.Vector3(),1.3);
    }
    const rim=ring(.72,profile.secondary);rim.rotation.x=1.2;rim.position.y=-.62;
  } else if(kind==='tasks') {
    const count=Math.min(12,Math.max(0,Math.trunc(Number(model.count)||0)));
    mesh(new THREE.OctahedronGeometry(.27),profile.secondary).userData.pinSpin=true;
    for(let i=0;i<count;i++) {
      const angle=i/Math.max(1,count)*Math.PI*2;
      const segment=mesh(new THREE.TorusGeometry(.7,.065,5,24,Math.PI*2/count*.72));
      segment.rotation.z=angle;segment.userData.pinPulse=i;
    }
  } else if(kind==='calendar') {
    slab(0,0,0,'#29465c');
    for(let i=0;i<2;i++){const bar=mesh(new THREE.CylinderGeometry(.04,.04,.28,8),profile.secondary);bar.position.set(i?.32:-.32,.36,.08);}
    const count=Math.min(6,model.items?.length||0);
    for(let i=0;i<count;i++){const dot=mesh(new THREE.BoxGeometry(.12,.1,.08));dot.position.set(-.28+(i%3)*.28,.12-Math.floor(i/3)*.24,.11);dot.userData.pinPulse=i;}
    ring(.78).userData.pinSpin=true;
  } else if(kind==='gmail') {
    slab(0,0,0,'#234457');
    const shape=new THREE.Shape();shape.moveTo(-.5,.32);shape.lineTo(0,-.04);shape.lineTo(.5,.32);
    const stroke=new THREE.Line(new THREE.BufferGeometry().setFromPoints(shape.getPoints(12).map(p=>new THREE.Vector3(p.x,p.y,.1))),
      new THREE.LineBasicMaterial({color:'#ff6c82'}));root.add(stroke);
    const letter=slab(0,.3,-.14,'#90d8ec');letter.scale.set(.78,.75,1);letter.userData.pinLift=true;
  } else if(kind==='whatsapp') {
    for(let i=0;i<2;i++) {
      const bubble=mesh(new THREE.SphereGeometry(.34,16,10),i?profile.secondary:profile.accent);
      bubble.scale.set(1.15,.78,.38);bubble.position.set(i?.24:-.24,i?.15:-.13,i?-.1:.1);bubble.userData.pinPulse=i;
      const tail=mesh(new THREE.ConeGeometry(.12,.24,3));tail.rotation.z=.65;tail.position.set(i?.42:-.4,i?-.04:-.34,.02);
    }
  } else if(kind==='system') {
    const values=[model.cpu_percent,model.ram_percent,model.gpu_percent];
    values.forEach((value,i)=>{
      if(!Number.isFinite(value))return;
      const arc=mesh(new THREE.TorusGeometry(.38+i*.19,.045,5,48,Math.max(.001,Math.min(100,Math.max(0,value))/100*Math.PI*2)),i===1?'#ff5e85':profile.accent);
      arc.position.z=i*.04;arc.rotation.z=Math.PI*.5;
    });
    mesh(new THREE.IcosahedronGeometry(.15),profile.secondary).userData.pinPulse=0;
  } else if(kind==='news') {
    for(let i=0;i<Math.min(3,model.items?.length||1);i++){
      const page=slab(i*.14-.14,i*.08,-i*.14,i===0?'#1d526b':'#233549');page.rotation.y=-.22;page.userData.pinPulse=i;
    }
    for(let i=0;i<3;i++) {const row=mesh(new THREE.BoxGeometry(i?.55:.28,.028,.015),profile.accent);row.position.set(i?.04:-.14,.14-i*.14,.07);}
  } else if(kind==='memory') {
    const points=[];
    for(let i=0;i<6;i++){
      const a=i/6*Math.PI*2;const item=mesh(new THREE.IcosahedronGeometry(.10),i%2?profile.secondary:profile.accent);
      item.position.set(Math.cos(a)*.64,Math.sin(a)*.55,Math.sin(a*2)*.2);item.userData.pinPulse=i;points.push(item.position.clone(),new THREE.Vector3());
    }
    root.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:profile.accent,transparent:true,opacity:.6})));
  } else if(kind==='search') {
    ring(.45,profile.accent).position.set(-.1,.1,0);
    const handle=mesh(new THREE.BoxGeometry(.10,.52,.10));handle.position.set(.35,-.35,0);handle.rotation.z=.75;
    ring(.78).userData.pinSpin=true;
  } else if(kind==='files') {
    for(let i=0;i<3;i++){const file=slab(i*.13-.13,i*.1-.1,-i*.14,i===0?'#23647b':'#204253');file.userData.pinPulse=i;}
  } else {
    const count=Math.min(5,model.items?.length||3);
    for(let i=0;i<count;i++){
      const bar=mesh(new THREE.BoxGeometry(.16,.25+i*.13,.12),i%2?profile.secondary:profile.accent);bar.position.set((i-(count-1)/2)*.25,-.2+i*.06,0);bar.userData.pinPulse=i;
    }
  }
  const base=ring(.88,profile.accent);base.rotation.x=1.18;base.position.y=-.65;
  base.userData.pinBase=true;
  root.children.forEach(item=>{item.userData.pinScale=item.scale.clone();item.userData.pinPosition=item.position.clone();});
  return root;
}

export function animatePinnedSymbol(root,time,reduced) {
  if(root.userData.pinKind==='memory')root.rotation.z=reduced?0:.08*Math.sin(time*.6);
  root.children.forEach((item,i)=>{
    if(item.userData.pinScale)item.scale.copy(item.userData.pinScale);
    if(item.userData.pinPosition)item.position.copy(item.userData.pinPosition);
    if(item.userData.pinSpin)item.rotation.z=reduced?0:time*.35;
    if(!reduced&&item.userData.pinPulse!==undefined){
      item.scale.multiplyScalar(1+.04*Math.sin(time*1.8+i));
      item.material.emissiveIntensity=.45+.18*(.5+.5*Math.sin(time*1.8+i));
    }
    if(!reduced&&item.userData.pinLift)item.position.y+=.12*(.5+.5*Math.sin(time*1.5));
    if(item.userData.pinCloud!==undefined&&!reduced)item.position.y+=.035*Math.sin(time*.7+i);
    if(!reduced&&item.userData.pinBase)item.rotation.z=time*.22;
    if(!reduced&&item.geometry?.type==='BoxGeometry'){
      if(root.userData.pinKind==='news' && item.userData.pinPulse!==undefined){
        item.position.y+=.07*Math.sin(time*.9+i*.7);
        item.rotation.y=-.22+.12*Math.sin(time*.6+i*.4);
      } else if(root.userData.pinKind==='files'){
        item.position.z+=.12*Math.sin(time*.8+i*.6);
      }
    }
    if(item.userData.pinRain){
      const {snow,count}=item.userData.pinRain,attribute=item.geometry.attributes.position,t=reduced?0:time;
      for(let n=0;n<count;n++) {
        const x=Math.sin(n*41.7)*.58,z=Math.cos(n*21.3)*.3,y=.02-((n/count+t*(snow?.18:.8))%1)*.65;
        const index=n*(snow?1:2);attribute.setXYZ(index,x,y,z);
        if(!snow)attribute.setXYZ(index+1,x+.016,y-.1,z);
      }
      attribute.needsUpdate=true;
    }
  });
}
