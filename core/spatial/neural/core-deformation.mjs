import * as THREE from 'three';
import {cortex} from './geometry.mjs';
import {morphGLSL} from './morph-timeline.mjs';

export function deformCore(core,uniforms){
  const originals=[];
  const prefix=`uniform float neuralMorph,neuralTime;attribute vec3 neuralTarget;${morphGLSL}
    vec3 neuralPosition(vec3 p){return neuralJourney(p,neuralTarget,fract(p.x*13.+p.y*17.),neuralMorph,neuralTime);}
    `;
  const materials=new Set();
  core.root.traverse(node=>{
    // Independent particles can scatter; connected triangles and lines must not tear.
    if(!node.material||!node.geometry||!node.isPoints)return;
    const positions=node.geometry.attributes.position;if(!positions)return;
    const target=new Float32Array(positions.count*3);
    for(let i=0;i<positions.count;i++){
      const x=positions.getX(i),y=positions.getY(i),z=positions.getZ(i),r=Math.max(.001,Math.hypot(x,y,z));
      cortex(x>=0?1:-1,Math.acos(THREE.MathUtils.clamp(y/r,-1,1)),Math.atan2(z,Math.abs(x)),THREE.MathUtils.clamp(r/1.5,.12,1)).multiplyScalar(1/.70).toArray(target,i*3);
    }
    node.geometry.setAttribute('neuralTarget',new THREE.BufferAttribute(target,3));
    const material=node.material;if(materials.has(material))return;materials.add(material);
    const old={material,onBeforeCompile:material.onBeforeCompile,customProgramCacheKey:material.customProgramCacheKey,vertexShader:material.vertexShader};originals.push(old);
    const bind=shader=>{shader.uniforms.neuralMorph=uniforms.uMorph;shader.uniforms.neuralTime=uniforms.uTime;};
    if(material.isShaderMaterial){bind(material);material.vertexShader=prefix+material.vertexShader.replace(/vec4\(position,\s*1\.0?\)/g,'vec4(neuralPosition(position),1.0)');}
    else {material.onBeforeCompile=function(shader,renderer){old.onBeforeCompile.call(this,shader,renderer);bind(shader);shader.vertexShader=prefix+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\ntransformed=neuralPosition(transformed);');};material.customProgramCacheKey=()=> 'neural-core-v1';}
    material.needsUpdate=true;
  });
  return ()=>{for(const old of originals){Object.assign(old.material,{onBeforeCompile:old.onBeforeCompile,customProgramCacheKey:old.customProgramCacheKey});if(old.vertexShader!==undefined)old.material.vertexShader=old.vertexShader;old.material.needsUpdate=true;}core.root.traverse(node=>node.geometry?.deleteAttribute('neuralTarget'));};
}
