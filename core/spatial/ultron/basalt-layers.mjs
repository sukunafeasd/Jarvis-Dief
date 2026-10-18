import * as THREE from './vendor/three.module.js';

function stratifiedRock(){
  const positions=[],normals=[],uvs=[];
  for(let layer=0;layer<3;layer++){
    const radius=1-layer*.17;
    const slab=new THREE.CylinderGeometry(radius*.93,radius,.43-layer*.04,7,1,false).toNonIndexed();
    slab.rotateX(Math.PI/2);slab.rotateZ(layer*.16);slab.translate(layer*.03,-layer*.02,-.39+layer*.36);
    positions.push(...slab.attributes.position.array);normals.push(...slab.attributes.normal.array);uvs.push(...slab.attributes.uv.array);slab.dispose();
  }
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('normal',new THREE.Float32BufferAttribute(normals,3));geometry.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));
  return geometry;
}

export class BasaltLayers {
  constructor(emission,relief,width,height,time){
    this.tiles=[];this.dummy=new THREE.Object3D();this.axis=new THREE.Vector3(0,0,1);
    let seed=57323;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
    const heatAt=(x,y)=>emission[(Math.max(0,Math.min(height-1,y))*width+((x%width+width)%width))*4]/255;
    for(let attempt=0;attempt<7000&&this.tiles.length<64;attempt++){
      const u=random(),v=.12+random()*.76,x=Math.floor(u*width),y=Math.floor((1-v)*height);
      if(heatAt(x,y)>.045)continue;
      const border=Math.max(heatAt(x+6,y),heatAt(x-6,y),heatAt(x,y+6),heatAt(x,y-6));
      if(border<.13)continue;
      const phi=u*Math.PI*2,theta=(1-v)*Math.PI;
      const normal=new THREE.Vector3(-Math.cos(phi)*Math.sin(theta),Math.cos(theta),Math.sin(phi)*Math.sin(theta));
      if(this.tiles.some(tile=>tile.normal.dot(normal)>.994))continue;
      this.tiles.push({normal,radius:1.68+relief[(y*width+x)*4]/255*.038-.015-.004,angle:random()*Math.PI*2,scale:new THREE.Vector3(.075+random()*.065,.045+random()*.04,.012+random()*.018),heat:border});
    }
    const geometry=stratifiedRock();geometry.setAttribute('rockHeat',new THREE.InstancedBufferAttribute(new Float32Array(this.tiles.map(tile=>tile.heat)),1));this.aperture={value:0};
    const material=new THREE.MeshStandardMaterial({color:0x3b3436,roughness:.95,metalness:.12});
    material.onBeforeCompile=shader=>{
      shader.uniforms.uRockTime=time;
      shader.uniforms.uLayerOpen=this.aperture;
      shader.vertexShader='attribute float rockHeat;varying float vRockHeat;varying vec3 vRockLocal;varying float vLayerFacing;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvRockHeat=rockHeat;vRockLocal=position;vec3 layerCenter=(modelMatrix*vec4(0.,0.,0.,1.)).xyz;vec3 layerWorld=(modelMatrix*instanceMatrix*vec4(position,1.)).xyz;vLayerFacing=dot(normalize(layerWorld-layerCenter),normalize(cameraPosition-layerCenter));');
      shader.fragmentShader='uniform float uRockTime;uniform float uLayerOpen;varying float vRockHeat;varying vec3 vRockLocal;varying float vLayerFacing;\n'+shader.fragmentShader.replace('#include <clipping_planes_fragment>','#include <clipping_planes_fragment>\nif(uLayerOpen>.02 && vLayerFacing>mix(1.,.89,uLayerOpen)) discard;').replace('#include <color_fragment>',`#include <color_fragment>
        float strata=.5+.5*sin(vRockLocal.z*39.+sin(vRockLocal.x*17.)*2.);
        diffuseColor.rgb*=mix(.72,1.07,strata);
      `).replace('#include <emissivemap_fragment>',`#include <emissivemap_fragment>
        float edge=smoothstep(.62,.94,length(vRockLocal.xy));
        totalEmissiveRadiance+=vec3(.45,.035,.003)*edge*vRockHeat*(.83+.17*sin(uRockTime*.5+vRockLocal.x*5.));
      `);
    };
    this.mesh=new THREE.InstancedMesh(geometry,material,this.tiles.length);this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);this.mesh.frustumCulled=false;
    const color=new THREE.Color();for(let i=0;i<this.tiles.length;i++){color.setScalar(.65+random()*.35);this.mesh.setColorAt(i,color);}
    this.update(0,new THREE.Vector3(0,0,1));
  }
  update(open,cameraFacing){
    this.aperture.value=open;
    for(let i=0;i<this.tiles.length;i++){
      const tile=this.tiles[i],threshold=THREE.MathUtils.lerp(1,.89,open);
      const visible=open>.02?1-THREE.MathUtils.smoothstep(tile.normal.dot(cameraFacing),threshold-.035,threshold-.008):1;
      this.dummy.position.copy(tile.normal).multiplyScalar(tile.radius);this.dummy.quaternion.setFromUnitVectors(this.axis,tile.normal);this.dummy.rotateZ(tile.angle);
      this.dummy.scale.copy(tile.scale).multiplyScalar(visible);this.dummy.updateMatrix();this.mesh.setMatrixAt(i,this.dummy.matrix);
    }
    this.mesh.instanceMatrix.needsUpdate=true;
  }
}

