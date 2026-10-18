import * as THREE from './vendor/three.module.js';

// Height and material response share the same lava mask, keeping molten seams recessed.
export function createCrustRelief(source,emissionPixels){
  const canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height;
  const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(source,0,0);
  const pixels=context.getImageData(0,0,canvas.width,canvas.height);
  for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++){
    const i=(y*canvas.width+x)*4;
    const light=(pixels.data[i]+pixels.data[i+1]+pixels.data[i+2])/765;
    const u=x/canvas.width*Math.PI*2,v=y/canvas.height*Math.PI;
    const strata=Math.sin(u*19+Math.sin(v*13)*2)*Math.sin(v*31+Math.sin(u*9));
    const grain=Math.sin(u*117+Math.sin(v*67))*Math.sin(v*93+Math.sin(u*43));
    const heat=emissionPixels[i]/255;
    const detail=THREE.MathUtils.clamp(.49+light*.21+strata*.1+grain*.04-heat*.36,.12,.88);
    const height=THREE.MathUtils.lerp(.49,detail,Math.sin(v)**2);
    pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=height*255;pixels.data[i+3]=255;
  }
  context.putImageData(pixels,0,0);
  const texture=new THREE.CanvasTexture(canvas);texture.wrapS=THREE.RepeatWrapping;
  return {texture,pixels:pixels.data,width:canvas.width,height:canvas.height};
}

