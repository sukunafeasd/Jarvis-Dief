import * as THREE from 'three';
import {coreProfile} from './core-profiles.mjs';
const smooth=(from,to,dt,speed=5)=>from+(to-from)*(1-Math.exp(-dt*speed));

export function createCoreMotion(core,surfaces){
  const motion={time:0,assembly:0,rest:1,level:0,speed:.26,energy:.05,luminosity:.62,voiceDirection:0,cueTime:0,cueSerial:null,cue:'',phase:'idle'};
  const matrix=new THREE.Object3D();
  const nodeAngles=Array.from({length:5},(_,i)=>i*1.26);
  return {
    state:motion,
    step(dt,input){
      const profile=coreProfile(input.phase),reduced=input.motion==='reduced';
      const projection=input.projection && !input.newsFusion;
      motion.time+=reduced?0:dt;
      for(const key of ['speed','energy','luminosity'])motion[key]=reduced?profile[key]:smooth(motion[key],profile[key],dt);
      const targetLevel=input.resting?0:Math.max(0,Math.min(1,input.level||0));
      motion.level=reduced?targetLevel:smooth(motion.level,targetLevel,dt,12);
      motion.rest=reduced?(input.resting ? .14 : 1):smooth(motion.rest,input.resting ? .14 : 1,dt,4.5);
      motion.assembly=reduced?1:Math.min(1,motion.assembly+dt/1.05);
      if(input.cue?.serial!==undefined&&motion.cueSerial!==input.cue.serial){
        motion.cueSerial=input.cue.serial;motion.cue=input.cue.kind;motion.cueTime=.85;
      }
      motion.cueTime=Math.max(0,motion.cueTime-dt);
      if(reduced)motion.cueTime=0;
      motion.phase=input.phase;
      const awake=(motion.rest-.14)/.86,activity=motion.level;
      const mode=input.environmentMode||'assistant';
      const minimal=mode==='focus'&&!input.newsFusion;
      core.root.userData.interactionRadius=minimal?1.05:1.95;
      const pace={assistant:1,analysis:.55,execution:1.8,focus:.18,exploration:.7}[mode]||1;
      const move=reduced?0:dt*(input.resting ? .12 : pace);
      const tilt={assistant:.08,analysis:.65,execution:-.48,focus:0,exploration:.32}[mode]||0;
      core.rings.rotation.x=reduced?tilt:smooth(core.rings.rotation.x,tilt,dt,3);
      core.rings.scale.setScalar(mode==='analysis'?1.12:mode==='execution'?1.06:minimal?.88:1);
      core.rings.visible=!minimal&&!projection;
      core.segments.visible=!minimal;
      const phase=motion.time;
      core.root.scale.setScalar(.82+.18*awake);
      core.root.position.z=-1.15*(1-awake);
      core.shell.rotation.y+=move*motion.speed*.085;
      core.orbit.rotation.y+=move*.022;
      core.rings.rotation.z+=move*motion.speed*.6;
      core.heart.rotation.y+=move*motion.energy*.55;
      core.rings.children.forEach((ring,i)=>ring.rotation.y+=move*motion.speed*(i%2?-.15:.19));
      core.segments.children.forEach((arc,i)=>arc.rotation.z+=move*motion.speed*(i%2?-1:1)*(.13+i*.016));
      core.heart.scale.setScalar((minimal?1.85:mode==='execution'?1.38:1.14)+activity*.085+(reduced?0:Math.sin(phase*.31)*.004));
      core.points.material.opacity=(motion.luminosity*.64+activity*.17)*motion.rest*motion.assembly;
      surfaces.membrane.material.uniforms.energy.value=motion.energy+activity*.35;
      for(const node of [surfaces.membrane,...surfaces.ribbons.children,surfaces.nodes]){
        const uniforms=node.material.uniforms;uniforms.time.value=phase;uniforms.assembly.value=motion.assembly;
        uniforms.visibility.value=motion.rest*(projection ? .18 : input.newsFusion ? .36 : 1);
        uniforms.alert.value=motion.cue==='warning'?motion.cueTime:0;
        uniforms.focus.value=motion.cueTime/.85;
      }
      surfaces.ribbons.children.forEach((ribbon,i)=>{
        ribbon.rotation.z+=move*motion.speed*(i%2?-.12:.12);
        ribbon.scale.setScalar(.97+.03*motion.assembly+activity*.018);
      });
      core.beacons.children.forEach((node,i)=>{
        nodeAngles[i]+=move*(.035+motion.energy*.20+i*.005);
        const angle=nodeAngles[i],tilt=.55+i*.31;
        const r=1.68+activity*.025;
        node.position.set(Math.cos(angle)*r,Math.sin(angle)*Math.cos(tilt)*r,Math.sin(angle)*Math.sin(tilt)*r);
        node.material.opacity=(.28+activity*.35)*motion.rest*motion.assembly;
        matrix.position.copy(node.position);matrix.scale.setScalar(1+activity*.18);matrix.updateMatrix();surfaces.nodes.setMatrixAt(i,matrix.matrix);
      });
      surfaces.nodes.instanceMatrix.needsUpdate=true;
      const positions=core.radial.geometry.attributes.position;
      motion.voiceDirection=reduced?(input.phase==='speaking'?1:0):smooth(motion.voiceDirection,input.phase==='speaking'?1:0,dt,7);
      const direction=motion.voiceDirection;
      const radius=1.66-direction*.38;
      for(let i=0;i<96;i++){
        const angle=i*Math.PI*2/96;
        const length=.006+activity*(.04+.10*Math.abs(Math.sin(i*.68+phase*6)));
        positions.setXYZ(i*2,Math.cos(angle)*radius,Math.sin(angle)*radius,.12);
        positions.setXYZ(i*2+1,Math.cos(angle)*(radius+length),Math.sin(angle)*(radius+length),.12);
      }
      positions.needsUpdate=true;core.radial.material.opacity=(.035+activity*.3)*motion.rest;
      core.pulses.children.forEach((ring,i)=>{
        const period=(phase+i*.47)%1.6;
        const audio=activity>.02&&['listening','speaking'].includes(input.phase);
        const cue=i===0&&motion.cueTime>0;
        ring.visible=(audio||cue)&&!input.resting&&!projection;
        const outgoing=.35+period*.95,incoming=1.88-period*.75;
        ring.scale.setScalar(cue?1.2+(.85-motion.cueTime)*.55:incoming+(outgoing-incoming)*direction);
        ring.material.opacity=cue?motion.cueTime*.09:(1-period/1.6)*activity*.22;
      });
      core.energySurface.material.uniforms.time.value=phase;
      core.energySurface.material.uniforms.visibility.value=motion.rest*motion.assembly;
      core.energySurface.material.uniforms.activity.value=motion.energy+activity*.45;
      core.shell.visible=!projection&&!minimal;core.heart.visible=!projection;
      core.orbit.visible=!minimal;
      core.beacons.visible=!minimal;
      surfaces.nodes.visible=!minimal;
      surfaces.ribbons.visible=!projection&&!minimal;
      return motion;
    }
  };
}
