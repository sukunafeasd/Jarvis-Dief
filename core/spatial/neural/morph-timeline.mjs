export const clamp01=value=>Math.max(0,Math.min(1,value));
export function smooth(a,b,x){const t=clamp01((x-a)/(b-a));return t*t*(3-2*t);}
export function stageAt(p){return p<.16?'awakening':p<.44?'dissolving':p<.62?'suspended':p<.91?'forming':'remembering';}
export const morphGLSL=`
vec3 neuralJourney(vec3 sphere,vec3 brain,float seed,float progress,float clock){
  float offset=fract(seed*7.13)*.12;
  float release=smoothstep(.12+offset,.36+offset,progress);
  float assembly=smoothstep(.55+offset,.89+offset*.65,progress);
  vec3 outward=normalize(sphere+vec3(.001));
  vec3 tangent=cross(outward,vec3(.12,1.,.07));
  vec3 drift=outward*(.24+.19*sin(seed*17.+1.));
  drift+=tangent*(.14*sin(seed*19.+clock*.28));
  drift+=vec3(sin(seed*41.+clock*.25),cos(seed*29.+clock*.21),sin(seed*31.))* .055;
  vec3 suspended=sphere+drift*release;
  return mix(suspended,brain,assembly);
}`;
