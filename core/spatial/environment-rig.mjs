// Both WebEngine surfaces use this projection and the same transaction timestamp.
export const clamp=(v,a=0,b=1)=>Math.min(b,Math.max(a,v));
export const smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
export function entranceDistance(entrance, now=Date.now(), reduced=false) {
  if(!entrance || reduced || !entrance.duration) return 0;
  const progress=smooth((now-entrance.at)/entrance.duration);
  let distance=(1-progress)*24;
  if(Number.isFinite(entrance.cancelAt) && now>=entrance.cancelAt) {
    const frozen=(1-smooth((entrance.cancelAt-entrance.at)/entrance.duration))*24;
    distance=frozen*(1-smooth((now-entrance.cancelAt)/320));
  }
  return Math.max(0,distance);
}
export function sceneDistance(state, now=Date.now(), reduced=state.motion==='reduced') {
  return reduced ? 0 : state.staging ? 24 : entranceDistance(state.entrance,now,false);
}
export function focusBlend(focus,now=Date.now(),reduced=false){
  if(!focus)return 0;
  return reduced?focus.to:focus.from+(focus.to-focus.from)*smooth((now-focus.at)/focus.duration);
}
export function observatoryCamera(state,focus,aspect=1,now=Date.now()){
  const travel=sceneDistance(state,now),reduced=state.motion==='reduced';
  const blend=focusBlend(focus,now,reduced),position=[travel*.07,travel*.015,3+travel],target=[0,0,-22];
  if(focus?.anchor){
    const [x,y,z,scale]=focus.anchor,radius=1.68*scale,mobile=aspect<.8;
    const dx=mobile?0:radius*1.7,dy=mobile?-radius*1.8:0;
    const end=[x+dx,y+dy,z+radius*(mobile?10:5.5)],aim=[x+dx,y+dy,z];
    for(let i=0;i<3;i++){position[i]+=(end[i]-position[i])*blend;target[i]+=(aim[i]-target[i])*blend;}
  }
  return {position,target,blend,moving:!reduced&&Boolean(focus&&focus.from!==focus.to&&now<focus.at+focus.duration)};
}
export function frameBudget(state, travelling=false) {
  if(!state.visible || state.motion==='reduced') return 0;
  return travelling || ['speaking','listening','thinking','executing'].includes(state.phase) ? 16 : 50;
}
export function rigTarget(state, now=Date.now()) {
  const distance=sceneDistance(state,now);
  const ambient={assistant:.72,analysis:.42,execution:.52,focus:.12,exploration:.9}[state.mode]??.72;
  return {distance,progress:1-distance/24,ambient:state.resting ? .3 : ambient,grid:0};
}
