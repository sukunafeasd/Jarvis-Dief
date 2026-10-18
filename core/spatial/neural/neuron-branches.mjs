import * as THREE from 'three';
import {neuralPaletteGLSL} from './palette.mjs';

export function neuronBranches(uniforms){
  const segments=32,branches=7,vertices=3*branches*segments*2;
  const positions=new Float32Array(vertices*3),along=new Float32Array(vertices),regions=new Float32Array(vertices);
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.BufferAttribute(positions,3).setUsage(THREE.DynamicDrawUsage));
  geometry.setAttribute('aAlong',new THREE.BufferAttribute(along,1));
  geometry.setAttribute('aRegion',new THREE.BufferAttribute(regions,1));
  for(let i=0;i<vertices;i++){along[i]=(Math.floor(i/2)%segments+(i%2))/segments;regions[i]=Math.floor(i/(branches*segments*2));}
  const material=new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,depthTest:false,blending:THREE.AdditiveBlending,
    vertexShader:`attribute float aAlong,aRegion;varying float vAlong,vRegion;void main(){vAlong=aAlong;vRegion=aRegion;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`${neuralPaletteGLSL}uniform float uTime,uMorph,uVoice,uFocus;varying float vAlong,vRegion;void main(){float travel=fract(uTime*.28-vRegion*.27);float impulse=exp(-pow((vAlong-travel)*21.,2.));float selected=1.-step(.1,abs(vRegion-uFocus));float reveal=smoothstep(.78+vRegion*.055,.87+vRegion*.055,uMorph);vec3 c=mix(vec3(.85,.12,.22),vec3(.18,.9,1.),selected*.85);gl_FragColor=vec4(neuralLight(c)*(1.+impulse*2.+uVoice),reveal*(.12+impulse*.65+uVoice*.14));}`});
  const root=new THREE.LineSegments(geometry,material);root.frustumCulled=false;
  const delta=new THREE.Vector3(),side=new THREE.Vector3(),a=new THREE.Vector3(),b=new THREE.Vector3(),p=new THREE.Vector3();
  function curve(start,end,t,bend){return p.copy(start).lerp(end,t).addScaledVector(side,Math.sin(t*Math.PI)*bend);}
  return {root,setCount(count){geometry.setDrawRange(0,Math.max(0,Math.min(3,count))*branches*segments*2);},update(index,start,end){
    delta.subVectors(end,start);side.set(-delta.y,delta.x,.2).normalize();
    for(let branch=0;branch<branches;branch++){
      if(branch===0){a.copy(start);b.copy(end);}
      else{
        const t=.15+branch*.105;
        a.copy(curve(start,end,t,.23));
        b.copy(a).addScaledVector(delta,.12).addScaledVector(side,(branch%2?1:-1)*(.14+branch*.025));
      }
      for(let j=0;j<=segments;j++){
        curve(a,b,j/segments,branch===0?.23:.07);
        if(j<segments)p.toArray(positions,((index*branches+branch)*segments*2+j*2)*3);
        if(j>0)p.toArray(positions,((index*branches+branch)*segments*2+(j-1)*2+1)*3);
      }
    }
    geometry.attributes.position.needsUpdate=true;
  }};
}
