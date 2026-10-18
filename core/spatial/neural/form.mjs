import * as THREE from 'three';
import {seeded,particleGeometry,foldedGeometry,neuralGeometry} from './geometry.mjs';
import {pointVertex,pointFragment,foldVertex,foldFragment,linkVertex,linkFragment} from './shaders.mjs';
import {corticalSurface,normalAlignment} from './cortical-surface.mjs';
import {synapses} from './synapses.mjs';
import {neuronBranches} from './neuron-branches.mjs';
import {deformCore} from './core-deformation.mjs';
import {NeuralLifecycle} from './lifecycle.mjs';
import {NeuralGlow} from './glow.mjs';
import {focusForNarration,voiceEnvelope} from './evidence-motion.mjs';

export class NeuralForm {
  constructor(scene,core,renderer){
    this.scene=scene;this.core=core;this.renderer=renderer;this.lifecycle=new NeuralLifecycle();this.elapsed=0;this.focus=-1;
    this.glow=new NeuralGlow(renderer);
    this.root=new THREE.Group();this.root.visible=false;scene.add(this.root);
    this.uniforms={uMorph:{value:0},uTime:{value:0},uVoice:{value:0},uDpr:{value:renderer.getPixelRatio()},uFocus:{value:-1},uTint:{value:new THREE.Color('#ff303b')},uAccent:{value:new THREE.Color('#ffccd3')}};
    this.palette='';this.white=new THREE.Color('#ffffff');
    const material=(vertexShader,fragmentShader)=>new THREE.ShaderMaterial({uniforms:this.uniforms,vertexShader,fragmentShader,transparent:true,depthWrite:false,depthTest:false,blending:THREE.AdditiveBlending});
    const random=seeded();
    this.root.add(new THREE.Points(particleGeometry(innerWidth<700?6000:9500,random),material(pointVertex,pointFragment)),new THREE.LineSegments(foldedGeometry(),material(foldVertex,foldFragment)));
    const cortex=corticalSurface(this.uniforms);this.cortexAlignment=normalAlignment(cortex.geometry);
    this.root.add(new THREE.LineSegments(neuralGeometry(random,650).geometry,material(linkVertex,linkFragment)),cortex);
    this.impulses=synapses(this.uniforms);this.root.add(this.impulses.root);
    this.dendrites=neuronBranches(this.uniforms);scene.add(this.dendrites.root);this.dendrites.root.visible=false;
    this.unbind=deformCore(core,this.uniforms);this.saved=[];this.materials=new Map();core.root.traverse(node=>{if(node.material&&!node.userData.newsProjection)this.materials.set(node.material,Boolean(node.isPoints));});
    this.deformedSurfaces=0;core.root.traverse(node=>{if(!node.isPoints&&node.geometry?.getAttribute('neuralTarget'))this.deformedSurfaces++;});
    this.labels=Array.from({length:3},(_,index)=>{
      const label=document.createElement('button');label.className='neural-fragment';label.hidden=true;
      label.append(document.createElement('strong'),document.createElement('q'),document.createElement('small'));
      label.addEventListener('click',()=>{this.focus=this.focus===index?-1:index;});document.body.append(label);return label;
    });
    this.status=document.createElement('div');this.status.className='neural-status';this.status.hidden=true;
    this.status.setAttribute('role','status');this.status.textContent='Aguardando o assunto da consulta';document.body.append(this.status);
    this.anchors=[new THREE.Vector3(-1.2,.65,.3),new THREE.Vector3(1.2,.1,.4),new THREE.Vector3(-.7,-.8,.3)];
  }
  update(payload){if(payload?.pending)this.focus=-1;this.lifecycle.update(payload);this.labels.forEach((label,i)=>{
    const item=this.lifecycle.items[i];if(!item){label.hidden=true;return;}
    label.children[0].textContent=item.title;label.children[1].textContent=item.detail.slice(0,180);
    label.children[2].textContent=[item.source,item.at,item.role==='assistant'?'Resposta anterior, nao comprovacao':''].filter(Boolean).join(' / ');
    label.title=item.detail;label.setAttribute('aria-label',item.title+': '+item.detail);
  });}
  restore(){for(const [material,opacity,visibility] of this.saved){material.opacity=opacity;if(visibility!==undefined)material.uniforms.visibility.value=visibility;}this.saved.length=0;}
  cancel(){this.lifecycle.cancel();this.status.hidden=true;this.labels.forEach(label=>label.hidden=true);}
  narrate(text){
    this.focus=focusForNarration(this.lifecycle.items,text);
  }
  step(dt,state,camera,elapsed=dt,color=state.color||'#ff303b'){
    const reduced=state.motion==='reduced',p=this.lifecycle.step(elapsed,{speaking:state.phase==='speaking',reduced});
    if(color!==this.palette){
      this.palette=color;this.uniforms.uTint.value.set(color);
      this.uniforms.uAccent.value.copy(this.uniforms.uTint.value).lerp(this.white,.65);
      document.body.style.setProperty('--neural-color','#'+this.uniforms.uTint.value.getHexString());
      document.body.style.setProperty('--neural-accent','#'+this.uniforms.uAccent.value.getHexString());
      document.body.dataset.neuralColor=color;
    }
    this.status.textContent=this.lifecycle.awaitingTopic?'Aguardando o assunto da consulta':this.lifecycle.outcome==='empty'?'Nenhuma lembranca relevante encontrada':this.lifecycle.outcome==='unavailable'?'Nao foi possivel consultar as lembrancas':'';
    this.status.hidden=!(this.lifecycle.awaitingTopic||this.lifecycle.outcome)||p<.6;
    document.body.dataset.neuralProgress=p.toFixed(3);document.body.dataset.neuralMemories=String(this.lifecycle.items.length);
    if(!this.lifecycle.active){
      this.uniforms.uMorph.value=0;this.uniforms.uVoice.value=0;
      this.root.visible=false;this.dendrites.root.visible=false;
      this.labels.forEach(label=>label.hidden=true);document.body.dataset.neuralVoice='0';return;
    }
    if(!reduced)this.elapsed+=dt;
    this.uniforms.uMorph.value=p;this.uniforms.uTime.value=this.elapsed;
    const targetVoice=state.phase==='speaking'?Number(state.level):0;
    this.uniforms.uVoice.value=reduced?0:voiceEnvelope(this.uniforms.uVoice.value,targetVoice,dt);
    this.uniforms.uFocus.value=this.focus;
    this.root.visible=p>.01;this.dendrites.root.visible=p>.78&&this.lifecycle.items.length>0;
    this.dendrites.setCount(this.lifecycle.items.length);
    this.core.root.visible=p<.64;
    this.root.position.copy(this.core.root.position);this.root.scale.copy(this.core.root.scale).multiplyScalar(1/.70);
    this.root.rotation.copy(this.core.root.rotation);this.root.rotation.x=THREE.MathUtils.lerp(this.root.rotation.x,.47,p);this.root.rotation.y=THREE.MathUtils.lerp(this.root.rotation.y,-.32,p);
    this.impulses.step(this.elapsed,p);this.root.updateMatrixWorld();camera.updateMatrixWorld();
    if(p>0)for(const [material,particles] of this.materials){
      const visibility=material.uniforms?.visibility?.value;this.saved.push([material,material.opacity,visibility]);
      const gain=1-THREE.MathUtils.smoothstep(p,particles?.22:.06,particles?.52:.22);
      material.opacity*=gain;if(visibility!==undefined)material.uniforms.visibility.value*=gain;
    }
    const compact=innerWidth<600,width=Math.min(compact?145:185,innerWidth*.34),margin=14;
    const positions=[[margin,innerHeight*.19],[innerWidth-width-margin,innerHeight*.52],[innerWidth*.30,innerHeight*.86]];
    this.labels.forEach((label,i)=>{
      label.hidden=!this.lifecycle.items[i]||p<([.8,.86,.92][i]);
      label.dataset.active=String(this.uniforms.uFocus.value===i);
      label.style.width=width+'px';
      const [x,y]=positions[i];const top=Math.min(y,innerHeight-label.offsetHeight-14);
      label.style.transform=`translate(${x}px,${top}px)`;
      const start=this.anchors[i].clone().applyMatrix4(this.root.matrixWorld);
      const z=start.clone().project(camera).z;
      const end=new THREE.Vector3((x+(i===1?0:width))/innerWidth*2-1,1-(top+6)/innerHeight*2,z).unproject(camera);
      this.dendrites.update(i,start,end);
    });
    document.body.dataset.neuralProgress=p.toFixed(3);document.body.dataset.neuralMemories=String(this.lifecycle.items.length);
    document.body.dataset.neuralVoice=this.uniforms.uVoice.value.toFixed(3);
  }
  render(camera){this.glow.render(this.renderer,this.scene,camera,this.lifecycle.progress);}
  dispose(){this.restore();this.unbind();this.glow.dispose();for(const root of [this.root,this.dendrites.root]){root.traverse(node=>{node.geometry?.dispose();node.material?.dispose();});this.scene.remove(root);}this.labels.forEach(label=>label.remove());this.status.remove();}
}
