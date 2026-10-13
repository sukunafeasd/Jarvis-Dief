import * as THREE from 'three';
import { profileFor } from './presentation_profiles.mjs';
import { surfaceFor } from './projection-style.mjs';

const quadVertex = `varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

// One screen-space pass: luminous conductors and a one-shot assembly scan.
export class HolographicPanelMotion {
  constructor() {
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 2);
    this.camera.position.z = 1;
    this.material = new THREE.ShaderMaterial({
      transparent: true, depthTest: false, depthWrite: false, toneMapped: false,
      uniforms: { size: {value:new THREE.Vector2(1,1)}, time: {value:0},
        assembly: {value:1}, focus: {value:0}, accent: {value:new THREE.Color('#35e5ff')},
        panel: {value:1}, compact: {value:0} },
      vertexShader: quadVertex,
      fragmentShader: `varying vec2 vUv;
        uniform vec2 size; uniform float time, assembly, focus, panel, compact;
        uniform vec3 accent;
        float glow(float d, float width) { return width * width / (width * width + d*d); }
        void main() {
          vec2 p = vec2(vUv.x, 1.0-vUv.y)*size;
          vec2 q = abs(p-size*.5) - (size*.5-vec2(5.0));
          float cut = mix(18.0,10.0,compact);
          float d = abs(max(max(q.x,q.y),(q.x+q.y+cut)*.7071));
          float traveling = pow(max(0.0, 1.0-abs(fract((p.x+p.y)*.0016-time*.055)-.5)*2.0),24.0);
          float breathe = .72+.28*sin(time*.8);
          float edge = glow(d,1.25)*(.09+.54*traveling+.25*focus);
          float halo = glow(d,8.0)*(.035+.08*traveling)*breathe;
          float formed = smoothstep(0.0,.5,assembly);
          float scan = glow(p.y-assembly*size.y,2.0)*(1.0-assembly)*.22;
          float corner = smoothstep(.25,.9,abs(vUv.x-.5)*2.0)*smoothstep(.25,.85,abs(vUv.y-.5)*2.0);
          vec3 color = mix(accent,vec3(1.0,.19,.25),corner);
          float alpha = clamp((edge+halo)*formed+scan,0.0,.7)*panel;
          if(alpha<.002) discard;
          gl_FragColor=vec4(color,alpha);
        }`,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.material);
    this.scene.add(this.mesh);
    this.started = 0;
  }

  begin(now) { this.started = now; }

  update(model, time, now, width, height, reduced, focus) {
    this.mesh.visible = Boolean(model.kind) && surfaceFor(model)==='card' && !model.framed;
    const u = this.material.uniforms;
    u.size.value.set(width,height);
    u.time.value = reduced ? 0 : time;
    u.assembly.value = reduced ? 1 : Math.min(1,Math.max(0,(now-this.started)/650));
    u.focus.value = reduced ? 0 : focus;
    u.accent.value.set(profileFor(model.kind).accent);
    u.panel.value = model.kind==='data' && document.body.dataset.factSymbol ? 0 : 1;
    u.compact.value = model.compact ? 1 : 0;
  }

  dispose() { this.mesh.geometry.dispose(); this.material.dispose(); this.scene.clear(); }
}

export class HolographicSymbolRig {
  constructor(model) {
    this.group = new THREE.Group();
    this.kind = model.kind;
    this.compact = Boolean(model.compact);
    const profile = profileFor(this.kind);
    this.rings = [];
    for(let i=0;i<2;i++) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(1.05+i*.10,this.compact ? .014 : .009,5,80,Math.PI*1.48),
        new THREE.MeshBasicMaterial({color:i?profile.secondary:profile.accent,
          transparent:true,opacity:.28,blending:THREE.AdditiveBlending,depthWrite:false,toneMapped:false}));
      ring.rotation.set(.68+i*.42,.30+i*.35,i*.8);
      this.group.add(ring); this.rings.push(ring);
    }
    const count = this.compact ? 12 : 24;
    const positions = new Float32Array(count*3), phases = new Float32Array(count);
    for(let i=0;i<count;i++) phases[i]=i/count;
    this.particles = new THREE.Points(new THREE.BufferGeometry()
      .setAttribute('position',new THREE.BufferAttribute(positions,3))
      .setAttribute('phase',new THREE.BufferAttribute(phases,1)), new THREE.ShaderMaterial({
        uniforms:{time:{value:0},color:{value:new THREE.Color(profile.accent)},
          intensity:{value:.3},speed:{value:1},size:{value:this.compact?4:5}},
        transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false,
        vertexShader:`attribute float phase; uniform float time,speed,size; varying float energy;
          void main() {
            float a=phase*6.283185+time*.28*speed;
            vec3 p=vec3(cos(a)*1.12,sin(a)*.36,sin(a)*.63);
            energy=.45+.55*sin(phase*6.283185+time*.6)*sin(phase*6.283185+time*.6);
            vec4 mv=modelViewMatrix*vec4(p,1.0);
            gl_Position=projectionMatrix*mv; gl_PointSize=size*(3.6/max(1.0,-mv.z));
          }`,
        fragmentShader:`uniform vec3 color; uniform float intensity; varying float energy;
          void main() {
            float r=length(gl_PointCoord-.5)*2.0;
            if(r>1.0) discard;
            gl_FragColor=vec4(color,pow(1.0-r,1.5)*intensity*energy);
          }`,
      }));
    // Shader-driven points have no CPU position updates, so keep their bounds explicit.
    this.particles.geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(),1.4);
    this.group.add(this.particles);
    this.stage = new THREE.Mesh(new THREE.PlaneGeometry(2.8,1.0),new THREE.ShaderMaterial({
      uniforms:{time:{value:0},color:{value:new THREE.Color(profile.accent)},focus:{value:0}},
      transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false,side:THREE.DoubleSide,
      vertexShader:quadVertex,
      fragmentShader:`varying vec2 vUv; uniform vec3 color; uniform float time,focus;
        void main() {
          float r=length((vUv-.5)*vec2(2.0,2.0));
          float rim=pow(max(0.0,1.0-abs(r-.72)*20.0),2.0);
          float inner=pow(max(0.0,1.0-r),3.0);
          float wave=pow(max(0.0,1.0-abs(r-fract(time*.28))*28.0),2.0)*.09;
          gl_FragColor=vec4(color,(rim*.20+inner*.08+wave)*(.8+focus));
        }`,
    }));
    this.stage.position.set(0,-.72,-.12);this.stage.rotation.x=-.65;
    this.group.add(this.stage);
    this.group.userData.holographicRig = true;
  }

  update(time, reduced, model, focus, progress) {
    const pace={calendar:.5,memory:.55,files:.65,weather:.6,tasks:.85,gmail:.75,whatsapp:.9};
    const speed=(pace[this.kind]||.75)*(this.compact ? .8 : 1);
    const t = reduced ? 0 : time;
    this.rings.forEach((ring,i)=>{
      ring.rotation.x = .68+i*.42 + .16*Math.sin(t*.32+i);
      ring.rotation.y = .30+i*.35 + .14*Math.cos(t*.27+i);
      ring.rotation.z = i*.8+t*(i?-.32:.40)*speed;
      ring.material.opacity = (.40+.12*Math.sin(t*.85+i)+focus*.3)*progress;
    });
    this.particles.material.uniforms.time.value=t;
    this.particles.material.uniforms.speed.value=speed;
    this.particles.material.uniforms.intensity.value=reduced ? .25 : (.65+focus*.3)*progress;
    this.stage.material.uniforms.time.value=t;
    this.stage.material.uniforms.focus.value=reduced ? 0 : focus;
    // Rain remains the weather's primary motion, not an orbit around the cloud.
    if(this.kind==='weather') {
      this.rings.forEach((ring,i)=>{ring.rotation.x=1.22+i*.1;ring.position.y=-.74;ring.scale.setScalar(.85+i*.05);});
      this.particles.visible=false;
    }
    this.particles.visible=this.kind!=='weather' && (this.kind!=='tasks' || model.count>0);
  }

  dispose() {
    this.group.traverse(object=>{object.geometry?.dispose();object.material?.dispose();});
    this.group.clear();
  }
}
