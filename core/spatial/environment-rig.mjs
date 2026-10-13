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
export function frameBudget(state, travelling=false) {
  if(!state.visible || state.motion==='reduced') return 0;
  return travelling || ['speaking','listening','thinking','executing'].includes(state.phase) ? 16 : 50;
}
export function rigTarget(state, now=Date.now()) {
  const distance=entranceDistance(state.entrance,now,state.motion==='reduced');
  const ambient={assistant:.72,analysis:.42,execution:.52,focus:.12,exploration:.9}[state.mode]??.72;
  return {distance,progress:1-distance/24,ambient:state.resting ? .3 : ambient,grid:0};
}
