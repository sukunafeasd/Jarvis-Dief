import * as THREE from 'three';
export class NeuralGlow {
  constructor(renderer){
    const type=renderer.extensions.has('EXT_color_buffer_float')?THREE.HalfFloatType:THREE.UnsignedByteType;
    this.target=new THREE.WebGLRenderTarget(1,1,{type,depthBuffer:true});
    this.a=new THREE.WebGLRenderTarget(1,1,{depthBuffer:false});this.b=this.a.clone();
    const vertexShader='varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}';
    this.blur=new THREE.ShaderMaterial({vertexShader,uniforms:{source:{value:null},direction:{value:new THREE.Vector2()},extract:{value:1}},fragmentShader:`uniform sampler2D source;uniform vec2 direction;uniform float extract;varying vec2 vUv;
    vec3 glow(vec2 p){vec3 c=texture2D(source,p).rgb;return mix(c,max(c-vec3(.24),0.),extract);}
    void main(){vec3 c=glow(vUv)*.227027;c+=glow(vUv+direction*1.384615)*.316216;c+=glow(vUv-direction*1.384615)*.316216;c+=glow(vUv+direction*3.230769)*.070270;c+=glow(vUv-direction*3.230769)*.070270;gl_FragColor=vec4(c,1.);}`});
    this.composite=new THREE.ShaderMaterial({vertexShader,uniforms:{base:{value:this.target.texture},glow:{value:this.b.texture},strength:{value:.3}},fragmentShader:`uniform sampler2D base,glow;uniform float strength;varying vec2 vUv;void main(){vec4 baseColor=texture2D(base,vUv);vec3 g=texture2D(glow,vUv).rgb*strength;vec3 c=vec3(1.)-exp(-(baseColor.rgb+g)*1.22);float a=max(baseColor.a,min(1.,max(g.r,max(g.g,g.b))));gl_FragColor=vec4(pow(c,vec3(.4545)),a);}`});
    this.scene=new THREE.Scene();this.camera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);this.quad=new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.blur);this.scene.add(this.quad);this.size=new THREE.Vector2();
  }
  render(renderer,scene,camera,progress=1){
    this.composite.uniforms.strength.value=.25+.35*THREE.MathUtils.smoothstep(progress,.75,1);
    renderer.getDrawingBufferSize(this.size);
    const scale=Math.min(1,1200/this.size.x,900/this.size.y);
    const w=Math.max(1,Math.round(this.size.x*scale)),h=Math.max(1,Math.round(this.size.y*scale));
    if(this.target.width!==w||this.target.height!==h){this.target.setSize(w,h);this.a.setSize(Math.max(1,Math.round(w/4)),Math.max(1,Math.round(h/4)));this.b.setSize(this.a.width,this.a.height);}
    renderer.setRenderTarget(this.target);renderer.render(scene,camera);
    this.quad.material=this.blur;this.blur.uniforms.source.value=this.target.texture;this.blur.uniforms.extract.value=1;this.blur.uniforms.direction.value.set(1.7/this.a.width,0);
    renderer.setRenderTarget(this.a);renderer.render(this.scene,this.camera);
    this.blur.uniforms.source.value=this.a.texture;this.blur.uniforms.extract.value=0;this.blur.uniforms.direction.value.set(0,1.7/this.b.height);
    renderer.setRenderTarget(this.b);renderer.render(this.scene,this.camera);
    this.quad.material=this.composite;renderer.setRenderTarget(null);renderer.render(this.scene,this.camera);
  }
  dispose(){this.target.dispose();this.a.dispose();this.b.dispose();this.blur.dispose();this.composite.dispose();this.quad.geometry.dispose();}
}
