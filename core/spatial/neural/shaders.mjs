import {morphGLSL} from './morph-timeline.mjs';
import {neuralPaletteGLSL} from './palette.mjs';
export const morphPosition=`
${morphGLSL}
vec3 transformPoint(vec3 sphere,vec3 brain,float seed){
  vec3 p=neuralJourney(sphere,brain,seed,uMorph,uTime);
  p*=1.0+uVoice*.012;
  return p;
}`;

export const pointVertex=`
uniform float uTime,uMorph,uVoice,uDpr,uFocus;
attribute vec3 aBrain,aSeed;
attribute float aSize,aRegion;
varying vec3 vColor;
varying float vAlpha;
${morphPosition}
void main(){
  vec3 p=transformPoint(position,aBrain,aSeed.x);
  p+=sin(uTime*.55+aSeed.y*42.0)*.007*normalize(aBrain);
  vec4 mv=modelViewMatrix*vec4(p,1.0);
  float neural=smoothstep(.4,.9,uMorph);
  float firing=pow(max(0.0,sin(uTime*(.7+aSeed.z)+aSeed.x*180.0)),48.0);
  float selected=1.0-step(.1,abs(aRegion-uFocus));
  vec3 red=mix(vec3(1.0,.012,.035),vec3(1.55,.07,.08),aSeed.y);
  red=mix(red,vec3(2.0,1.1,.8),firing*.6);
  vColor=mix(red,vec3(.19,.85,.96),selected*neural*.72);
  float airy=mix(.85,1.0,smoothstep(.65,.95,uMorph));
  vAlpha=(.12+aSeed.z*.15+firing*.30)*(1.0+uVoice*.55)*airy;
  vec3 normal=normalize(normalMatrix*normalize(aBrain*vec3(.8,1.0,.72)));
  vAlpha*=mix(.16,1.0,smoothstep(-.18,.9,normal.z));
  vAlpha*=smoothstep(.10,.45,uMorph);
  gl_Position=projectionMatrix*mv;
  gl_PointSize=clamp(aSize*uDpr*(17.0/-mv.z)*(1.0+firing*.4),1.0,10.0);
}`;
export const pointFragment=`
${neuralPaletteGLSL}
varying vec3 vColor;
varying float vAlpha;
void main(){
  float r=length(gl_PointCoord-.5)*2.0;
  if(r>1.0)discard;
  float hot=exp(-r*r*28.0),halo=exp(-r*r*7.0)*.08;
  gl_FragColor=vec4(neuralLight(vColor),clamp((hot+halo)*vAlpha,0.0,.95));
}`;

export const foldVertex=`
uniform float uTime,uMorph,uVoice;
attribute vec3 aBrain;
attribute float aWeight;
varying float vAlpha;
${morphPosition}
void main(){
  vec3 p=transformPoint(position,aBrain,aWeight);
  vec4 mv=modelViewMatrix*vec4(p,1.0);
  vec3 normal=normalize(normalMatrix*normalize(aBrain*vec3(.8,1.0,.72)));
  vAlpha=aWeight*smoothstep(.65,.95,uMorph)*(.018+.25*smoothstep(-.1,.9,normal.z));
  vAlpha*=1.0+uVoice*.7;
  gl_Position=projectionMatrix*mv;
}`;
export const foldFragment=`
${neuralPaletteGLSL}
varying float vAlpha;
void main(){gl_FragColor=vec4(neuralLight(vec3(1.7,.035,.065)),vAlpha);}`;

export const linkVertex=`
uniform float uTime,uMorph,uVoice,uFocus;
attribute vec3 aBrain;
attribute float aAlong,aSeed,aRegion;
varying float vAlong,vSeed,vSelected,vFront;
${morphPosition}
void main(){
  vec3 p=transformPoint(position,aBrain,aSeed);
  vAlong=aAlong;vSeed=aSeed;vSelected=1.0-step(.1,abs(aRegion-uFocus));
  vFront=mix(.3,1.0,smoothstep(-1.2,1.4,p.z));
  gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.0);
}`;
export const linkFragment=`
${neuralPaletteGLSL}
uniform float uTime,uMorph,uVoice;
varying float vAlong,vSeed,vSelected,vFront;
void main(){
  float travel=fract(uTime*(.21+vSeed*.15)+vSeed*13.0);
  float head=exp(-pow((vAlong-travel)*17.0,2.0));
  float enabled=step(.61,sin(vSeed*171.0+uTime*.38));
  float alpha=(.018+head*enabled*(.34+uVoice*.4))*smoothstep(.70,.96,uMorph)*vFront;
  vec3 color=mix(vec3(1.0,.12,.2),vec3(.18,.83,1.0),vSelected*.75);
  color=mix(color,vec3(1.0,.88,.7),head*.5*(1.0-vSelected));
  gl_FragColor=vec4(neuralLight(color),alpha);
}`;
