import * as THREE from './vendor/three.module.js';
import { machinedMetal } from './machined-metal.mjs';

export class PlanetInterior {
  constructor(texture,emission){
    this.group=new THREE.Group();
    this.shell=new THREE.Mesh(new THREE.SphereGeometry(1.59,64,48),new THREE.MeshStandardMaterial({
      map:texture,bumpMap:texture,bumpScale:.035,color:0x1a1318,metalness:.72,roughness:.78,
      emissive:0xba230f,emissiveMap:emission,emissiveIntensity:.24,side:THREE.BackSide}));
    this.group.add(this.shell);
    this.throat=new THREE.Group();this.group.add(this.throat);
    const metal=machinedMetal({color:0x28303a,metalness:.87,roughness:.62,side:THREE.DoubleSide});
    const hot=new THREE.MeshStandardMaterial({color:0x38160c,emissive:0xff5c1c,emissiveIntensity:1.4,metalness:.68,roughness:.5});
    const wall=new THREE.Mesh(new THREE.CylinderGeometry(.795,.65,.66,72,5,true),metal);
    wall.rotation.x=Math.PI/2;wall.position.z=1.14;this.throat.add(wall);
    const scorched=new THREE.MeshStandardMaterial({map:texture,bumpMap:texture,bumpScale:.04,color:0x24120e,metalness:.16,roughness:.94});
    const lip=new THREE.Mesh(new THREE.TorusGeometry(.775,.031,10,96),scorched);lip.position.z=1.485;this.throat.add(lip);
    const mantle=new THREE.Mesh(new THREE.TorusGeometry(.75,.011,6,96),hot);mantle.position.z=1.477;this.throat.add(mantle);
    this.turbine=new THREE.Group();this.throat.add(this.turbine);
    const blades=new THREE.InstancedMesh(new THREE.BoxGeometry(.032,.14,.045),metal,24);const dummy=new THREE.Object3D();
    for(let i=0;i<24;i++){
      const angle=i/24*Math.PI*2;
      dummy.position.set(Math.cos(angle)*.57,Math.sin(angle)*.57,.75);dummy.rotation.set(.2,0,angle-.35);dummy.updateMatrix();blades.setMatrixAt(i,dummy.matrix);
    }
    this.turbine.add(blades);
    this.ribs=[];
    for(let i=0;i<4;i++){
      const radius=.65+i*.047,z=.81+i*.22;
      const ring=new THREE.Mesh(new THREE.TorusGeometry(radius,.022,8,96),metal);ring.position.z=z;this.throat.add(ring);
      const seam=new THREE.Mesh(new THREE.TorusGeometry(radius-.025,.006,4,96),hot);seam.position.z=z+.004;this.throat.add(seam);this.ribs.push(seam);
    }
    this.reactorHousing=new THREE.Group();this.group.add(this.reactorHousing);
    const casing=new THREE.Mesh(new THREE.TorusGeometry(.72,.08,10,96),metal);casing.position.z=-.12;this.reactorHousing.add(casing);
    for(let i=0;i<16;i++){
      const angle=i/16*Math.PI*2;
      const tile=new THREE.Mesh(new THREE.BoxGeometry(.07,.14,.11),metal);
      tile.position.set(Math.cos(angle)*.76,Math.sin(angle)*.76,-.06);tile.rotation.z=angle;this.reactorHousing.add(tile);
      const source=new THREE.Mesh(new THREE.BoxGeometry(.012,.07,.025),hot);source.position.copy(tile.position);source.position.z+=.07;source.rotation.z=angle;this.reactorHousing.add(source);
    }
    this.axis=new THREE.Vector3(0,0,1);this.direction=new THREE.Vector3();
  }
  update(time,open,direction,motion){
    this.direction.copy(direction).normalize();this.throat.quaternion.setFromUnitVectors(this.axis,this.direction);
    const cut=THREE.MathUtils.lerp(1,.89,open);
    const radius=Math.sqrt(Math.max(0,1-cut*cut))/Math.sqrt(1-.89*.89);
    this.throat.scale.set(radius,radius,1);this.throat.visible=open>.02;
    this.reactorHousing.rotation.z=time*-.09;
    this.turbine.rotation.z=time*.13;
    this.shell.rotation.y=time*.025;
    this.shell.material.emissiveIntensity=.18+open*.16+Math.sin(time*1.2)*.025*motion;
    for(const rib of this.ribs)rib.material.emissiveIntensity=1.05+open*.6+Math.sin(time*1.8)*.15*motion;
  }
}

