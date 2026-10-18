import * as THREE from 'three';

export function seeded(seed=8127){return ()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};}

// Two joined cerebral domes, not an ellipsoid with a brain texture on it.
export function cortex(side,phi,theta,depth=1){
  const sp=Math.sin(phi),cp=Math.cos(phi),ct=Math.cos(theta),st=Math.sin(theta);
  const fold=.055*Math.sin(13*theta+2.5*Math.sin(6*phi))+.026*Math.sin(22*phi+2*Math.cos(7*theta));
  const r=depth*(1+fold);
  let x=side*(.09+1.30*sp*ct*r);
  let y=1.08*cp*r;
  let z=1.42*sp*st*r;
  x*=1+.07*st-.04*cp;
  y+=.08*st-.10*Math.max(0,-cp);
  y-=.27*Math.exp(-Math.pow(x/.34,2))*Math.max(0,cp);
  z*=1+.09*cp;
  return new THREE.Vector3(x,y,z);
}

export function corePoint(target,index){
  const n=target.clone().normalize();
  return n.multiplyScalar(.98+.035*Math.sin(index*1.17));
}

export function particleGeometry(count,random){
  const p=[],brain=[],seed=[],region=[],size=[];
  for(let i=0;i<count;i++){
    const side=i%2?1:-1;
    const phi=Math.acos(1-2*random());
    const theta=(random()-.5)*Math.PI;
    const volume=random()<.33;
    const depth=volume?.25+.74*Math.cbrt(random()):.99+random()*.025;
    const b=cortex(side,phi,theta,depth);
    const s=corePoint(b,i).multiplyScalar(volume?.35+.63*Math.cbrt(random()):1);
    p.push(...s.toArray());brain.push(...b.toArray());
    seed.push(random(),random(),random());region.push(regionOf(b));
    size.push((volume?.7:1.0)+Math.pow(random(),6)*2.2);
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(p,3));
  g.setAttribute('aBrain',new THREE.Float32BufferAttribute(brain,3));
  g.setAttribute('aSeed',new THREE.Float32BufferAttribute(seed,3));
  g.setAttribute('aRegion',new THREE.Float32BufferAttribute(region,1));
  g.setAttribute('aSize',new THREE.Float32BufferAttribute(size,1));
  return g;
}

export function regionOf(p){return p.y>.28?0:p.z>.05?1:2;}

export function foldedGeometry(){
  const points=[],brain=[],seed=[];
  let idx=0;
  function segment(a,b,weight){
    for(const v of [a,b]){points.push(...corePoint(v,idx++).toArray());brain.push(...v.toArray());seed.push(weight);}
  }
  for(const side of [-1,1]){
    for(let line=0;line<18;line++){
      const base=.16+line/18*(Math.PI-.32);
      let prev;
      for(let j=0;j<=100;j++){
        const t=j/100,theta=(t-.5)*Math.PI;
        const phi=base+.065*Math.sin(theta*6+line*.85)+.03*Math.sin(theta*15+line);
        const p=cortex(side,phi,theta,1.012);
        if(prev)segment(prev,p,.82);prev=p;
      }
    }
    for(let line=0;line<10;line++){
      let prev;
      for(let j=0;j<=70;j++){
        const phi=.12+j/70*(Math.PI-.24);
        const theta=(line/9-.5)*Math.PI+.052*Math.sin(phi*11+line);
        const p=cortex(side,phi,theta,1.005);
        if(prev)segment(prev,p,.20);prev=p;
      }
    }
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(points,3));
  g.setAttribute('aBrain',new THREE.Float32BufferAttribute(brain,3));
  g.setAttribute('aWeight',new THREE.Float32BufferAttribute(seed,1));
  return g;
}

export function neuralGeometry(random,count=900){
  const nodes=[];
  for(let i=0;i<count;i++)nodes.push(cortex(i%2?1:-1,Math.acos(1-2*random()),(random()-.5)*Math.PI,.22+.78*Math.cbrt(random())));
  const pos=[],target=[],fraction=[],seeds=[],regions=[];
  let edges=0;
  // Local links preserve regional structure; a few commissural links cross the fissure.
  for(let i=0;i<count;i++){
    const neighbors=[];
    for(let j=i+1;j<count;j++){
      const distance=nodes[i].distanceToSquared(nodes[j]);
      if(distance<.22)neighbors.push([distance,j]);
    }
    neighbors.sort((a,b)=>a[0]-b[0]);
    for(const [,j] of neighbors.slice(0,3)){
      const a=nodes[i],b=nodes[j],phase=random();
      for(let k=0;k<2;k++){
        const v=k?b:a;
        pos.push(...corePoint(v,i).toArray());target.push(...v.toArray());
        fraction.push(k);seeds.push(phase);regions.push(regionOf(v));
      }
      edges++;
    }
  }
  const g=new THREE.BufferGeometry();
  for(const [name,array,itemSize] of [['position',pos,3],['aBrain',target,3],['aAlong',fraction,1],['aSeed',seeds,1],['aRegion',regions,1]])g.setAttribute(name,new THREE.Float32BufferAttribute(array,itemSize));
  return {geometry:g,nodes,edges};
}
