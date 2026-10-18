import * as THREE from './vendor/three.module.js';

export function machinedMetal(parameters){
  const canvas=document.createElement('canvas');canvas.width=256;canvas.height=128;
  const context=canvas.getContext('2d');const image=context.createImageData(256,128);
  let seed=61583;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
  for(let y=0;y<128;y++){
    const brush=180+random()*35;
    for(let x=0;x<256;x++){
      const i=(y*256+x)*4,grain=brush+(random()-.5)*12;
      image.data[i]=image.data[i+1]=image.data[i+2]=grain;image.data[i+3]=255;
    }
  }
  context.putImageData(image,0,0);
  const texture=new THREE.CanvasTexture(canvas);texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(3,1);
  return new THREE.MeshStandardMaterial({...parameters,bumpMap:texture,bumpScale:.007,roughnessMap:texture});
}

