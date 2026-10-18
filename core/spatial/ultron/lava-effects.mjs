import * as THREE from './vendor/three.module.js';

export class LavaActivity {
  constructor(pixels,width,height,reliefPixels=null){
    this.group=new THREE.Group();this.vents=[];this.bursts=0;this.active=0;
    let seed=46815;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
    for(let attempt=0;attempt<2400&&this.vents.length<22;attempt++){
      const u=random(),v=.18+random()*.64,x=Math.min(width-1,Math.floor(u*width)),y=Math.min(height-1,Math.floor((1-v)*height));
      if(pixels[(y*width+x)*4]<185)continue;
      const phi=u*Math.PI*2,theta=(1-v)*Math.PI;
      const normal=new THREE.Vector3(-Math.cos(phi)*Math.sin(theta),Math.cos(theta),Math.sin(phi)*Math.sin(theta));
      if(this.vents.some(vent=>vent.normal.dot(normal)>.96))continue;
      const tangent=new THREE.Vector3().crossVectors(normal,new THREE.Vector3(0,1,0));if(tangent.lengthSq()<.01)tangent.set(1,0,0);tangent.normalize();
      const surfaceRadius=1.68+(reliefPixels?reliefPixels[(y*width+x)*4]/255*.038-.015:0);
      this.vents.push({normal,tangent,bitangent:new THREE.Vector3().crossVectors(normal,tangent),radius:surfaceRadius+.002,period:5.5+random()*4,offset:random()*8,strength:.78+random()*.44,previousCycle:-1});
    }
    this.count=this.vents.length*5;
    this.positions=new Float32Array(this.count*3);this.colors=new Float32Array(this.count*3);this.sizes=new Float32Array(this.count);
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(this.positions,3).setUsage(THREE.DynamicDrawUsage));geometry.setAttribute('color',new THREE.BufferAttribute(this.colors,3).setUsage(THREE.DynamicDrawUsage));geometry.setAttribute('sparkSize',new THREE.BufferAttribute(this.sizes,1).setUsage(THREE.DynamicDrawUsage));
    const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,depthTest:true,vertexColors:true,blending:THREE.AdditiveBlending,
      uniforms:{pixelScale:{value:1}},vertexShader:`attribute float sparkSize;uniform float pixelScale;varying vec3 vColor;void main(){vColor=color;vec4 view=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*view;gl_PointSize=clamp(sparkSize*pixelScale*180./max(1.,-view.z),0.,15.);}`,
      fragmentShader:`varying vec3 vColor;void main(){float r=length(gl_PointCoord-.5);if(r>.5)discard;float light=exp(-r*r*20.);gl_FragColor=vec4(vColor*light*2.2,light*.9);}`});
    this.sparks=new THREE.Points(geometry,material);this.sparks.frustumCulled=false;this.group.add(this.sparks);
    this.trailPositions=new Float32Array(this.count*4*3);this.trailColors=new Float32Array(this.count*4*3);this.trailSizes=new Float32Array(this.count*4);
    const trailGeometry=new THREE.BufferGeometry();trailGeometry.setAttribute('position',new THREE.BufferAttribute(this.trailPositions,3).setUsage(THREE.DynamicDrawUsage));trailGeometry.setAttribute('color',new THREE.BufferAttribute(this.trailColors,3).setUsage(THREE.DynamicDrawUsage));trailGeometry.setAttribute('sparkSize',new THREE.BufferAttribute(this.trailSizes,1).setUsage(THREE.DynamicDrawUsage));
    this.trails=new THREE.Points(trailGeometry,material.clone());this.trails.frustumCulled=false;this.group.add(this.trails);
    this.fragments=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(.027,0),new THREE.MeshStandardMaterial({color:0x28150f,emissive:0xff3607,emissiveIntensity:.95,roughness:.87,metalness:.4}),this.count);this.fragments.instanceMatrix.setUsage(THREE.DynamicDrawUsage);this.fragments.frustumCulled=false;this.group.add(this.fragments);
    this.ripples=new THREE.InstancedMesh(new THREE.TorusGeometry(.03,.004,4,24),new THREE.MeshBasicMaterial({color:0xd94714,transparent:true,opacity:.26,blending:THREE.AdditiveBlending,depthWrite:false}),this.vents.length);this.ripples.instanceMatrix.setUsage(THREE.DynamicDrawUsage);this.ripples.frustumCulled=false;this.group.add(this.ripples);
    const plumeGeometry=new THREE.ConeGeometry(.055,1,8,5,true);plumeGeometry.translate(0,.5,0);plumeGeometry.rotateX(Math.PI/2);
    const plumeMaterial=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,
      uniforms:{time:{value:0}},vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*instanceMatrix*vec4(position,1.);}`,
      fragmentShader:`uniform float time;varying vec2 vUv;void main(){float taper=sin(vUv.y*3.14159);float flow=.6+.4*sin(vUv.y*27.-time*9.+sin(vUv.x*18.849556)*2.);vec3 heat=mix(vec3(1.,.12,.008),vec3(1.,.64,.19),vUv.y);gl_FragColor=vec4(heat*1.8,taper*flow*.22);}`});
    this.plumes=new THREE.InstancedMesh(plumeGeometry,plumeMaterial,this.vents.length);this.plumes.instanceMatrix.setUsage(THREE.DynamicDrawUsage);this.plumes.frustumCulled=false;this.group.add(this.plumes);
    this.blisters=new THREE.InstancedMesh(new THREE.SphereGeometry(.036,12,8),new THREE.MeshStandardMaterial({color:0x602008,emissive:0xff4708,emissiveIntensity:1.15,metalness:.18,roughness:.29}),this.vents.length);this.blisters.instanceMatrix.setUsage(THREE.DynamicDrawUsage);this.blisters.frustumCulled=false;this.group.add(this.blisters);
    this.dummy=new THREE.Object3D();this.point=new THREE.Vector3();this.rippleColor=new THREE.Color();this.axis=new THREE.Vector3(0,0,1);this.lastTime=0;
  }
  update(time,motion,open,cameraFacing,pixelRatio){
    this.lastTime=time;this.active=0;this.sparks.material.uniforms.pixelScale.value=pixelRatio;this.trails.material.uniforms.pixelScale.value=pixelRatio;this.plumes.material.uniforms.time.value=time;
    this.trails.visible=motion>.3;
    for(let ventIndex=0;ventIndex<this.vents.length;ventIndex++){
      const vent=this.vents[ventIndex];const cycle=Math.floor((time+vent.offset)/vent.period),age=(time+vent.offset)%vent.period;
      const cut=open>.02&&vent.normal.dot(cameraFacing)>THREE.MathUtils.lerp(1,.89,open);
      if(cycle!==vent.previousCycle){if(vent.previousCycle>=0)this.bursts++;vent.previousCycle=cycle;}
      const enabled=!cut&&motion>.3,erupt=age<1.65&&enabled;if(erupt)this.active++;
      const rippleFade=erupt?Math.sin(Math.PI*age/1.65):0;
      this.dummy.position.copy(vent.normal).multiplyScalar(vent.radius);this.dummy.quaternion.setFromUnitVectors(this.axis,vent.normal);this.dummy.scale.set(erupt?1+age*.8:0,erupt?1+age*.8:0,rippleFade);this.dummy.updateMatrix();this.ripples.setMatrixAt(ventIndex,this.dummy.matrix);
      this.rippleColor.setRGB(rippleFade,rippleFade,rippleFade);this.ripples.setColorAt(ventIndex,this.rippleColor);
      const jet=erupt?Math.sin(Math.PI*age/1.65):0;this.dummy.scale.set(.6+jet*.7,.6+jet*.7,jet*.27*vent.strength);this.dummy.updateMatrix();this.plumes.setMatrixAt(ventIndex,this.dummy.matrix);
      const blisterClear=open<=.02||vent.normal.dot(cameraFacing)<THREE.MathUtils.lerp(1,.89,open)-.025;
      const blister=enabled&&blisterClear&&age<.42?Math.sin(Math.PI*age/.42):0;
      this.dummy.position.copy(vent.normal).multiplyScalar(vent.radius-.005);this.dummy.scale.set(blister*vent.strength,blister*vent.strength,blister*.55);this.dummy.updateMatrix();this.blisters.setMatrixAt(ventIndex,this.dummy.matrix);
      for(let particle=0;particle<5;particle++){
        const index=ventIndex*5+particle,life=age-particle*.09;
        const alive=enabled&&life>0&&life<1.88;
        const lift=alive?Math.max(0,.62*life-.33*life*life)*vent.strength:0;
        const spread=alive?life*.12:0,angle=particle*2.39996+ventIndex*.71;
        this.point.copy(vent.normal).multiplyScalar(vent.radius+lift).addScaledVector(vent.tangent,Math.cos(angle)*spread).addScaledVector(vent.bitangent,Math.sin(angle)*spread);
        this.positions[index*3]=this.point.x;this.positions[index*3+1]=this.point.y;this.positions[index*3+2]=this.point.z;
        const heat=alive?Math.max(0,1-life/1.88):0;this.colors[index*3]=heat;this.colors[index*3+1]=heat*heat*.40;this.colors[index*3+2]=heat*heat*.06;this.sizes[index]=heat*.4;
        this.dummy.position.copy(this.point);this.dummy.rotation.set(life*3+particle,life*2+ventIndex,life*4);this.dummy.scale.setScalar(heat*(.65+particle*.12));this.dummy.updateMatrix();this.fragments.setMatrixAt(index,this.dummy.matrix);
        if(this.trails.visible)for(let sample=0;sample<4;sample++){
          const trailIndex=index*4+sample,past=life-(sample+1)*.035;
          const glow=alive&&past>0?heat*(1-sample/4)*.38:0;
          const height=glow>0?Math.max(0,.62*past-.33*past*past)*vent.strength:0;
          this.point.copy(vent.normal).multiplyScalar(vent.radius+height).addScaledVector(vent.tangent,Math.cos(angle)*Math.max(0,past)*.12).addScaledVector(vent.bitangent,Math.sin(angle)*Math.max(0,past)*.12);
          this.trailPositions[trailIndex*3]=this.point.x;this.trailPositions[trailIndex*3+1]=this.point.y;this.trailPositions[trailIndex*3+2]=this.point.z;
          this.trailColors[trailIndex*3]=glow;this.trailColors[trailIndex*3+1]=glow*heat*.22;this.trailColors[trailIndex*3+2]=glow*.012;this.trailSizes[trailIndex]=glow*.34;
        }
      }
    }
    this.sparks.geometry.attributes.position.needsUpdate=true;this.sparks.geometry.attributes.color.needsUpdate=true;this.sparks.geometry.attributes.sparkSize.needsUpdate=true;this.fragments.instanceMatrix.needsUpdate=true;this.ripples.instanceMatrix.needsUpdate=true;this.plumes.instanceMatrix.needsUpdate=true;
    if(this.ripples.instanceColor)this.ripples.instanceColor.needsUpdate=true;
    this.blisters.instanceMatrix.needsUpdate=true;
    if(this.trails.visible)for(const attribute of Object.values(this.trails.geometry.attributes))attribute.needsUpdate=true;
  }
  diagnostics(){return {vents:this.vents.length,active:this.active,bursts:this.bursts,particles:this.count,trailSamples:this.count*4};}
}

