import * as THREE from 'three';
import {cortex,corePoint} from './geometry.mjs';
import {morphGLSL} from './morph-timeline.mjs';
import {neuralPaletteGLSL} from './palette.mjs';

export function normalAlignment(geometry){
  const p=geometry.attributes.position,n=geometry.attributes.normal;let sum=0,count=0;
  for(let i=0;i<p.count;i+=31){
    const length=Math.hypot(p.getX(i),p.getY(i),p.getZ(i));
    if(length>.1){sum+=(p.getX(i)*n.getX(i)+p.getY(i)*n.getY(i)+p.getZ(i)*n.getZ(i))/length;count++;}
  }
  return count?sum/count:0;
}

export function corticalSurface(uniforms){
  const positions=[],sources=[],indices=[];
  const rows=52,columns=76;
  for(const side of [-1,1]){
    const base=positions.length/3;
    for(let row=0;row<=rows;row++)for(let col=0;col<=columns;col++){
      const p=cortex(side,.012+row/rows*(Math.PI-.024),-.5*Math.PI+col/columns*Math.PI,.985);
      positions.push(...p.toArray());sources.push(...corePoint(p,row*columns+col).toArray());
    }
    for(let row=0;row<rows;row++)for(let col=0;col<columns;col++){
      const a=base+row*(columns+1)+col,b=a+columns+1;
      if(side===1)indices.push(a,a+1,b,a+1,b+1,b);else indices.push(a,b,a+1,a+1,b,b+1);
    }
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  geometry.setAttribute('aSphere',new THREE.Float32BufferAttribute(sources,3));
  geometry.setIndex(indices);geometry.computeVertexNormals();
  const material=new THREE.ShaderMaterial({uniforms,transparent:true,side:THREE.FrontSide,depthWrite:false,
    vertexShader:`uniform float uMorph,uTime;attribute vec3 aSphere;varying vec3 vNormal,vView,vP;
      ${morphGLSL}
      void main(){vec3 p=mix(aSphere,position,smoothstep(.57,.93,uMorph));vec4 view=modelViewMatrix*vec4(p,1.);vNormal=normalize(normalMatrix*normal);vView=normalize(-view.xyz);vP=position;gl_Position=projectionMatrix*view;}`,
    fragmentShader:`${neuralPaletteGLSL}uniform float uMorph,uVoice,uTime;varying vec3 vNormal,vView,vP;
      void main(){vec3 n=normalize(vNormal);float facing=abs(dot(n,normalize(vView)));float rim=pow(1.-facing,2.2);
        float key=pow(max(0.,dot(n,normalize(vec3(-.3,.8,1.)))),3.);
        float ridge=sin(vP.y*19.+sin(vP.z*11.)*2.5+sin(vP.x*14.));
        float grain=sin(vP.x*197.+vP.z*127.)*sin(vP.y*171.-vP.z*99.);
        float glint=pow(max(0.,dot(reflect(-normalize(vec3(-.4,.65,1.)),n),normalize(vView))),32.);
        float signal=pow(.5+.5*sin(vP.y*8.-vP.z*5.-uTime*.8),16.);
        vec3 base=vec3(.012,.0015,.006)+vec3(.12,.004,.012)*key;
        base+=vec3(.70,.04,.065)*rim+vec3(.50,.25,.25)*glint;
        base+=vec3(.15,.008,.016)*pow(max(0.,ridge),14.)+grain*.0015;
        base+=vec3(.12,.06,.06)*signal*uVoice;
        gl_FragColor=vec4(neuralLight(base)*(1.+uVoice*.35),smoothstep(.77,.98,uMorph)*(.25+rim*.24));}`
  });
  const mesh=new THREE.Mesh(geometry,material);mesh.renderOrder=-5;mesh.frustumCulled=false;return mesh;
}
