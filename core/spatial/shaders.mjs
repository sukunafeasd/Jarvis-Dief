import * as THREE from "three";

const vertex = `varying vec3 vNormal; varying vec3 vView; varying vec3 vPosition;
void main(){ vec4 view=modelViewMatrix*vec4(position,1.0); vView=normalize(-view.xyz); vNormal=normalize(normalMatrix*normal); vPosition=position; gl_Position=projectionMatrix*view; }`;

export const MATERIAL_PROFILES = Object.freeze({
  DATA_SURFACE: { color: 0xc1d4dd, alpha: 0.62 },
  HOLOGRAPHIC_NEUTRAL: { color: 0x8ea9b5, alpha: 0.3 },
  HOLOGRAPHIC_ACTIVE: { color: 0xaeefff, alpha: 0.5 },
  WARNING: { color: 0xeebd75, alpha: 0.5 },
  CRITICAL: { color: 0xed7c81, alpha: 0.6 },
});
export function holographicMaterial(profile = "HOLOGRAPHIC_NEUTRAL") {
  const values = MATERIAL_PROFILES[profile];
  if (!values) throw Error("Material nao autorizado.");
  return new THREE.ShaderMaterial({
    vertexShader: vertex,
    transparent: true,
    depthWrite: false,
    uniforms: {
      tint: { value: new THREE.Color(values.color) },
      alpha: { value: values.alpha },
      assembly: { value: 0 },
      illumination: { value: 1 },
    },
    fragmentShader: `varying vec3 vNormal; varying vec3 vView; varying vec3 vPosition; uniform vec3 tint; uniform float alpha; uniform float assembly; uniform float illumination;
  void main(){
    float edge=pow(1.0-abs(dot(normalize(vNormal),normalize(vView))),2.5);
    float keyLight=0.35+max(0.0,dot(normalize(vNormal),normalize(vec3(-0.4,0.7,1.0))))*0.45;
    float reveal=smoothstep(0.0,0.1,assembly-vPosition.y*0.12);
    gl_FragColor=vec4(tint*(keyLight*illumination+edge*0.2),alpha*reveal*(0.62+edge*0.32));
    #include <colorspace_fragment>
  }`,
  });
}

// Shared thin-film edge response, no fullscreen bloom or chromatic aberration.
export function energyMaterial(color) {
  return new THREE.ShaderMaterial({
    vertexShader: vertex,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      tint: { value: new THREE.Color(color) },
      time: { value: 0 },
      activity: { value: 0.05 },
      visibility: { value: 1 },
    },
    fragmentShader: `varying vec3 vNormal; varying vec3 vView; varying vec3 vPosition; uniform vec3 tint; uniform float time; uniform float activity; uniform float visibility;
    void main(){ float edge=pow(1.0-abs(dot(normalize(vNormal),normalize(vView))),2.4);
      float flow=sin(vPosition.y*17.0+sin(vPosition.x*11.0+time*.6)+time*.9)*.5+.5;
      float fine=sin(vPosition.y*160.0)*.5+.5;
      float micro=sin(vPosition.x*123.0+vPosition.z*89.0)*sin(vPosition.y*117.0)*.5+.5;
      float alpha=(.055+edge*.17+flow*.035)*( .65+activity*.35 );
      gl_FragColor=vec4(tint*(.58+edge*.55+flow*.08+micro*.025),alpha*(.96+fine*.02+micro*.02)*visibility); }`,
  });
}

export function cloudMaterial(color) {
  return new THREE.ShaderMaterial({
    vertexShader: vertex,
    transparent: true,
    depthWrite: false,
    uniforms: {
      tint: { value: new THREE.Color(color) },
      time: { value: 0 },
      storm: { value: 0 },
      keyLight: { value: 1 },
    },
    fragmentShader: `varying vec3 vNormal; varying vec3 vView; varying vec3 vPosition; uniform vec3 tint; uniform float time; uniform float storm; uniform float keyLight;
    void main(){ vec3 n=normalize(vNormal); float edge=pow(1.0-abs(dot(n,normalize(vView))),1.8);
      float light=.32+max(0.0,dot(n,normalize(vec3(-.5,.8,1.0))))*.5;
      float density=.42+.08*sin(vPosition.x*9.0+sin(vPosition.y*11.0)+time*.04)+.05*sin(vPosition.z*13.+vPosition.y*7.-time*.03);
      gl_FragColor=vec4(tint*(light*keyLight+storm*.1)+vec3(edge*.025),density*(1.0-edge*.88));
      #include <colorspace_fragment>
    }`,
  });
}
