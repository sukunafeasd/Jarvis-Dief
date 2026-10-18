import * as THREE from 'three';

export function coreSkinMaterial(color){
  return new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.FrontSide,
    uniforms:{tint:{value:new THREE.Color(color)},time:{value:0},energy:{value:0},visibility:{value:1},assembly:{value:1},alert:{value:0},focus:{value:0},solid:{value:0}},
    vertexShader:`varying vec3 n;varying vec3 view;varying vec3 p;
      void main(){vec4 local=vec4(position,1.);vec3 localNormal=normal;
        #ifdef USE_INSTANCING
          local=instanceMatrix*local;localNormal=mat3(instanceMatrix)*localNormal;
        #endif
        vec4 v=modelViewMatrix*local;n=normalize(normalMatrix*localNormal);view=normalize(-v.xyz);p=position;gl_Position=projectionMatrix*v;}`,
    fragmentShader:`varying vec3 n;varying vec3 view;varying vec3 p;uniform vec3 tint;uniform float time,energy,visibility,assembly,alert,focus,solid;
      void main(){
        vec3 normal=normalize(n);float rim=pow(1.-abs(dot(normal,normalize(view))),2.8);
        float key=max(0.,dot(normal,normalize(vec3(-.45,.65,1.))));
        float grain=sin(p.x*147.+p.z*53.)*sin(p.y*129.-p.z*71.);
        float interference=sin(p.y*23.+sin(p.x*11.)+time*.18)*.5+.5;
        float etching=smoothstep(.985,.999,cos(p.y*46.))*smoothstep(.15,.8,key);
        float brushed=sin(p.x*63.+p.z*29.)*grain;
        float reflection=pow(max(0.,dot(reflect(-normalize(vec3(-.45,.65,1.)),normal),normalize(view))),24.);
        float fill=pow(max(0.,dot(normal,normalize(vec3(.8,-.2,.5)))),5.);
        float contour=pow(max(0.,dot(normal,normalize(vec3(.65,.35,-.75)))),8.);
        float satin=pow(max(0.,dot(reflect(-normalize(vec3(.7,.2,1.)),normal),normalize(view))),48.);
        float seam=smoothstep(.96,1.,cos(atan(p.z,p.x)*12.))*smoothstep(.88,1.,cos(p.y*18.));
        float conductor=pow(.5+.5*sin(atan(p.z,p.x)*6.-p.y*4.-time*.55),28.);
        float signal=conductor*pow(key,3.)*(.012+energy*.045);
        float reveal=smoothstep(-.08,.08,assembly*3.16-1.58-p.y);
        vec3 steel=vec3(.008,.012,.018)+tint*(.08+key*.14)+brushed*.001;
        vec3 edgeTint=mix(tint,vec3(.94,.64,.27),alert*.55);
        vec3 highlight=mix(edgeTint,vec3(.98,.75,.65),.08)*(rim*(.72+focus*.07)+pow(key,12.)*.18+reflection*.065);
        gl_FragColor=vec4(steel+highlight+vec3(.65,.76,.84)*(fill*.012+satin*.038)+tint*(solid*(.48+key*.35)+contour*.05+interference*.014+etching*.013+seam*.018+signal)+grain*.0015,min(1.,.12+rim*.46+solid*.62+energy*.04)*visibility*reveal);
        #include <colorspace_fragment>
      }`});
}

export function addCoreSurfaces(core){
  const membrane=new THREE.Mesh(new THREE.IcosahedronGeometry(1.485,4),coreSkinMaterial('#5be8ff'));
  membrane.renderOrder=-1;core.shell.add(membrane);
  const ribbons=new THREE.Group();core.root.add(ribbons);
  for(let i=0;i<6;i++){
    const values=[],indices=[],radius=1.18+i*.052;
    for(let j=0;j<=48;j++){
      const a=j/48*Math.PI*.70;
      for(const band of [-.009,.009])values.push(Math.cos(a)*(radius+band),Math.sin(a)*(radius+band),.018*Math.sin(a*3+i));
      if(j<48){const k=j*2;indices.push(k,k+1,k+2,k+1,k+3,k+2);}
    }
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(values,3));geometry.setIndex(indices);geometry.computeVertexNormals();
    const ribbon=new THREE.Mesh(geometry,coreSkinMaterial('#acd7df'));
    ribbon.material.side=THREE.DoubleSide;ribbon.rotation.set(i*.44,i*.31,i*.9);ribbons.add(ribbon);
  }
  const nodes=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(.063,2),coreSkinMaterial('#d9eef0'),5);
  nodes.material.uniforms.solid.value=1;
  nodes.instanceMatrix.setUsage(THREE.DynamicDrawUsage);nodes.frustumCulled=false;core.root.add(nodes);
  return {membrane,ribbons,nodes};
}
