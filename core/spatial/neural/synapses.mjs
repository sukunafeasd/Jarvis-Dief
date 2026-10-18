import * as THREE from 'three';
import {cortex} from './geometry.mjs';
import {neuralPaletteGLSL} from './palette.mjs';

export function synapses(uniforms){
  const root=new THREE.Group(),curves=[],regions=[],positions=[],along=[],seeds=[],ids=[];
  for(let region=0;region<3;region++)for(let lane=0;lane<4;lane++){
    const side=lane%2?1:-1;
    const a=cortex(side,.5+region*.7,-.9+lane*.45,.86);
    const b=cortex(-side,.75+region*.6,.7-lane*.37,.88);
    const mid=a.clone().lerp(b,.5);mid.z+=.65;mid.y+=.13*Math.sin(lane);
    const curve=new THREE.CatmullRomCurve3([a,a.clone().lerp(mid,.55),mid,mid.clone().lerp(b,.55),b]);
    curves.push(curve);regions.push(region);
    for(let j=0;j<60;j++)for(const k of [j,j+1]){
      positions.push(...curve.getPoint(k/60).toArray());along.push(k/60);seeds.push(lane*.19+region*.23);ids.push(region);
    }
  }
  const g=new THREE.BufferGeometry();
  for(const [name,array,size] of [['position',positions,3],['aAlong',along,1],['aSeed',seeds,1],['aRegion',ids,1]])g.setAttribute(name,new THREE.Float32BufferAttribute(array,size));
  const lines=new THREE.LineSegments(g,new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,depthTest:false,blending:THREE.AdditiveBlending,
    vertexShader:`attribute float aAlong,aSeed,aRegion;varying float vAlong,vSeed,vRegion;void main(){vAlong=aAlong;vSeed=aSeed;vRegion=aRegion;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`${neuralPaletteGLSL}uniform float uTime,uMorph,uFocus;varying float vAlong,vSeed,vRegion;
      void main(){float head=fract(uTime*.12+vSeed);float pulse=exp(-pow((vAlong-head)*11.,2.));float selected=1.-step(.1,abs(vRegion-uFocus));float reveal=smoothstep(.70,.94,uMorph);vec3 c=mix(vec3(1.8,.12,.10),vec3(.25,1.5,1.8),selected);gl_FragColor=vec4(neuralLight(c),(.025+pulse*.62)*reveal*(.35+selected*.65));}`
  }));root.add(lines);
  const particles=curves.length*9;
  const particleGeometry=new THREE.BufferGeometry();
  particleGeometry.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(particles*3),3));
  const alpha=[],regionIds=[];
  for(let i=0;i<curves.length;i++)for(let tail=0;tail<9;tail++){alpha.push(Math.pow(1-tail/9,1.5));regionIds.push(regions[i]);}
  particleGeometry.setAttribute('aAlpha',new THREE.Float32BufferAttribute(alpha,1));
  particleGeometry.setAttribute('aRegion',new THREE.Float32BufferAttribute(regionIds,1));
  const heads=new THREE.Points(particleGeometry,new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,depthTest:false,blending:THREE.AdditiveBlending,
    vertexShader:`uniform float uDpr;attribute float aAlpha,aRegion;varying float vAlpha,vRegion;void main(){vAlpha=aAlpha;vRegion=aRegion;vec4 p=modelViewMatrix*vec4(position,1.);gl_PointSize=(3.+aAlpha*5.)*uDpr*(7./-p.z);gl_Position=projectionMatrix*p;}`,
    fragmentShader:`${neuralPaletteGLSL}uniform float uMorph,uFocus;varying float vAlpha,vRegion;void main(){float r=length(gl_PointCoord-.5)*2.;if(r>1.)discard;float selected=1.-step(.1,abs(vRegion-uFocus));vec3 c=mix(vec3(2.,.9,.5),vec3(.6,2.,2.4),selected);gl_FragColor=vec4(neuralLight(c),exp(-r*r*5.)*vAlpha*smoothstep(.70,.94,uMorph)*(.3+selected*.7));}`
  }));root.add(heads);
  const point=new THREE.Vector3();
  return {root,routeCount:curves.length,step(time,morph){
    root.visible=morph>.65;
    const attr=particleGeometry.attributes.position;
    for(let i=0;i<curves.length;i++)for(let tail=0;tail<9;tail++){
      const t=((time*.12+(i%4)*.19+Math.floor(i/4)*.23-tail*.012)%1+1)%1;
      curves[i].getPoint(t,point);attr.setXYZ(i*9+tail,point.x,point.y,point.z);
    }
    attr.needsUpdate=true;
  }};
}
