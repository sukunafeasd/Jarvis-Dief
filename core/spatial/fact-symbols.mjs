import * as THREE from 'three';

export function factSymbolFor(model) {
  if (model.kind !== 'data' || model.error || model.compact || (model.items?.length || 0) > 4) return '';
  const title = String(model.title || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  if (/caloria|kcal|gasto calorico/.test(title)) return 'flame';
  if (/energia|bateria|carga/.test(title)) return 'energy';
  if (/passos|caminhada|distancia|treino|atividade fisica/.test(title)) return 'steps';
  return '';
}

export function buildFactSymbol(kind) {
  const root = new THREE.Group();
  const color = kind === 'energy' ? '#35f5a5' : '#ffb52d';
  let glyphIndex=0;
  function outline(shape, x = 0, y = 0, scale = 1) {
    const geometry = new THREE.ExtrudeGeometry(shape, {depth: .06, bevelEnabled: true,
      bevelSize: .009, bevelThickness: .01, bevelSegments: 2, curveSegments: 24, steps: 1});
    const surface = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color,
      emissive: color, emissiveIntensity: .9, roughness: .19, metalness: .25,
      transparent: true, opacity: .32, depthWrite: false}));
    const points = shape.getPoints(90).map(p => new THREE.Vector3(p.x, p.y, .09));
    const edge = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points, true),
      96, .020, 6, true), new THREE.MeshBasicMaterial({color, transparent: true,
        opacity: .95, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false}));
    const halo = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points, true),
      96, .072, 6, true), new THREE.MeshBasicMaterial({color, transparent: true,
        opacity: .18, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false}));
    surface.add(halo);
    surface.add(edge); surface.position.set(x, y, .08); surface.scale.setScalar(scale);
    surface.userData.factGlyph=kind;surface.userData.glyphIndex=glyphIndex++;
    root.add(surface);
  }
  if (kind === 'steps') {
    for (let i = 0; i < 2; i++) {
      const foot = new THREE.Shape(); foot.moveTo(-.09, -.30);
      foot.bezierCurveTo(-.15, -.25, -.10, -.08, -.13, .04);
      foot.bezierCurveTo(-.25, .41, .23, .45, .14, .10);
      foot.bezierCurveTo(.08, -.05, .15, -.24, .08, -.30); foot.closePath();
      outline(foot, i ? .23 : -.23, i ? -.12 : .13);
    }
  } else if (kind === 'flame') {
    const flame = new THREE.Shape(); flame.moveTo(0, -.43);
    flame.bezierCurveTo(-.44, -.38, -.36, .02, -.16, .17);
    flame.bezierCurveTo(-.17, -.02, -.02, -.05, .01, .12);
    flame.bezierCurveTo(.10, .35, -.01, .39, .05, .53);
    flame.bezierCurveTo(.18, .32, .51, -.29, .16, -.40); flame.closePath();
    outline(flame);
  } else {
    const battery = new THREE.Shape(); battery.moveTo(-.38, -.22);
    battery.lineTo(.30, -.22); battery.lineTo(.30, -.10); battery.lineTo(.39, -.10);
    battery.lineTo(.39, .10); battery.lineTo(.30, .10); battery.lineTo(.30, .22);
    battery.lineTo(-.38, .22); battery.closePath(); outline(battery);
    const bolt = new THREE.Shape(); bolt.moveTo(.03, .29); bolt.lineTo(-.17, -.03);
    bolt.lineTo(-.03, -.03); bolt.lineTo(-.08, -.29); bolt.lineTo(.17, .06);
    bolt.lineTo(.03, .06); bolt.closePath(); outline(bolt, 0, 0, .7);
  }
  for (let i = 0; i < 3; i++) {
    const curve = new THREE.EllipseCurve(0, 0, .98, .36, 0, Math.PI * 2);
    const points = curve.getPoints(120).map(p => new THREE.Vector3(p.x, p.y, -.12));
    const orbit = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({color: '#c5edff', transparent: true, opacity: .6,
        depthWrite: false, blending: THREE.AdditiveBlending}));
    orbit.rotation.z = i * Math.PI / 3; orbit.userData.factOrbit = i;
    root.add(orbit);
  }
  const base = new THREE.Mesh(new THREE.TorusGeometry(.77, .005, 4, 80),
    new THREE.MeshBasicMaterial({color: '#74d9ef', transparent: true, opacity: .38, depthWrite: false}));
  base.rotation.x = Math.PI / 2.5; base.position.y = -.63; root.add(base);
  const ticks = [];
  for (let i = 0; i < 48; i++) {
    const a = i / 48 * Math.PI * 2;
    const r = i % 4 === 0 ? .84 : .81;
    ticks.push(new THREE.Vector3(Math.cos(a)*.77, -.63+Math.sin(a)*.24, .01),
      new THREE.Vector3(Math.cos(a)*r, -.63+Math.sin(a)*r*.31, .01));
  }
  root.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(ticks),
    new THREE.LineBasicMaterial({color, transparent:true, opacity:.45, depthWrite:false})));
  return root;
}
