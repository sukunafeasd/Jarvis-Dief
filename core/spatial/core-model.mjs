import * as THREE from "three";
import { energyMaterial } from "./shaders.mjs";
const PALETTE = {amber:"#ffae4e",cyan:"#5be8ff",paleAmber:"#ffe6a8",paleCyan:"#d0ffff"};
function seeded(seed) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}
export function buildCore(theme = "amber", economy = false) {
  const random = seeded(1021);
  const root = new THREE.Group();
  const color = new THREE.Color(
    theme === "amber" ? PALETTE.amber : PALETTE.cyan,
  );
  const pale = new THREE.Color(
    theme === "amber" ? PALETTE.paleAmber : PALETTE.paleCyan,
  );
  const shell = new THREE.Group();
  root.add(shell);
  const count = economy ? 1050 : 2400;
  const positions = [];
  const colors = [];
  const vectors = [];
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const angle = Math.PI * (3 - Math.sqrt(5)) * i;
    const r = 1.5 + (random() - 0.5) * 0.11;
    const point = new THREE.Vector3(
      Math.cos(angle) * radius * r,
      y * r,
      Math.sin(angle) * radius * r,
    );
    vectors.push(point);
    positions.push(...point.toArray());
    const tint = color.clone().lerp(pale, random() * 0.7);
    colors.push(tint.r, tint.g, tint.b);
  }
  const pointsGeo = new THREE.BufferGeometry();
  pointsGeo.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  pointsGeo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  const sprite = document.createElement("canvas");
  sprite.width = sprite.height = 32;
  const ctx = sprite.getContext("2d");
  const glow = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
  glow.addColorStop(0, "rgba(255,255,255,1)");
  glow.addColorStop(0.10, "rgba(255,255,255,.95)");
  glow.addColorStop(0.34, "rgba(255,255,255,.24)");
  glow.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, 32, 32);
  const texture = new THREE.CanvasTexture(sprite);
  const points = new THREE.Points(
    pointsGeo,
    new THREE.PointsMaterial({
      size: 0.038,
      map: texture,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  shell.add(points);
  const links = [];
  for (let i = 0; i < count; i++) {
    for (const gap of [34, 55]) {
      const next = (i + gap) % count;
      if (vectors[i].distanceTo(vectors[next]) < 0.38)
        links.push(...vectors[i].toArray(), ...vectors[next].toArray());
    }
  }
  const linksGeo = new THREE.BufferGeometry();
  linksGeo.setAttribute("position", new THREE.Float32BufferAttribute(links, 3));
  shell.add(
    new THREE.LineSegments(
      linksGeo,
      new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: 0.30,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    ),
  );
  const meridians = [];
  for (let band = 0; band < 12; band++)
    for (let step = 0; step < 80; step++) {
      if (step % 7 === 0) continue;
      for (const part of [step, step + 1]) {
        const latitude = -Math.PI / 2 + (part / 80) * Math.PI;
        const longitude =
          (band / 12) * Math.PI * 2 + Math.sin(latitude * 8 + band) * 0.022;
        const r = 1.535;
        meridians.push(
          Math.cos(latitude) * Math.cos(longitude) * r,
          Math.sin(latitude) * r,
          Math.cos(latitude) * Math.sin(longitude) * r,
        );
      }
    }
  const circuitGeo = new THREE.BufferGeometry().setAttribute(
    "position",
    new THREE.Float32BufferAttribute(meridians, 3),
  );
  shell.add(
    new THREE.LineSegments(
      circuitGeo,
      new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: 0.24,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    ),
  );
  const rings = new THREE.Group();
  root.add(rings);
  for (let ring = 0; ring < 5; ring++) {
    const geo = new THREE.BufferGeometry();
    const values = [];
    const radius = 0.38 + ring * 0.25;
    for (let i = 0; i < 240; i++) {
      if ((i + ring * 7) % (37 + ring * 3) < 5) continue;
      const a = (i / 240) * Math.PI * 2;
      for (const step of [a, a + (Math.PI * 2) / 240])
        values.push(
          Math.cos(step) * radius,
          Math.sin(step) * radius,
          Math.sin(step * 4 + ring) * 0.035,
        );
    }
    const line = new THREE.LineSegments(
      geo.setAttribute("position", new THREE.Float32BufferAttribute(values, 3)),
      new THREE.LineBasicMaterial({
        color: ring < 2 ? pale : color,
        transparent: true,
        opacity: ring < 2 ? 0.38 : 0.2,
        blending: THREE.AdditiveBlending,
      }),
    );
    line.rotation.set(ring * 0.29, ring * 0.35, ring * 0.24);
    rings.add(line);
  }
  const detailGeo = new THREE.BufferGeometry();
  const detail = [];
  for (let i = 0; i < (economy ? 120 : 260); i++) {
    const a = random() * Math.PI * 2;
    const r = 0.13 + random() * 0.35;
    detail.push(Math.cos(a) * r, Math.sin(a) * r, (random() - 0.5) * 0.6);
  }
  detailGeo.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(detail, 3),
  );
  const heart = new THREE.Points(
    detailGeo,
    new THREE.PointsMaterial({
      color: pale,
      size: 0.035,
      map: texture,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  root.add(heart);
  const filaments = [];
  for (let strand = 0; strand < (economy ? 18 : 40); strand++) {
    const offset = random() * Math.PI * 2,
      tilt = random() * Math.PI;
    for (let step = 0; step < 45; step++)
      for (const part of [step, step + 1]) {
        const a = (part / 45) * Math.PI * 2 + offset,
          r = 0.26 + Math.sin(a * 3 + strand) * 0.085;
        const x = Math.cos(a) * r,
          y = Math.sin(a) * r;
        filaments.push(x, y * Math.cos(tilt), y * Math.sin(tilt));
      }
  }
  const filamentGeo = new THREE.BufferGeometry().setAttribute(
    "position",
    new THREE.Float32BufferAttribute(filaments, 3),
  );
  heart.add(
    new THREE.LineSegments(
      filamentGeo,
      new THREE.LineBasicMaterial({
        color: pale,
        transparent: true,
        opacity: 0.38,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    ),
  );
  const light = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: texture,
      color: pale,
      transparent: true,
      opacity: 0.32,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  light.scale.set(0.8, 0.8, 1);
  heart.add(light);
  const energySurface = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.34, economy ? 2 : 4),
    energyMaterial(pale),
  );
  heart.add(energySurface);
  const scan = new THREE.Group();
  root.add(scan);
  // Fixed rim geometry shares the existing rig and its motion/disposal lifecycle.
  for (const [radius, thickness, length, angle] of [
    [1.54, .008, Math.PI * 2, 0],
    [1.64, .018, Math.PI * .38, .38],
    [1.69, .018, Math.PI * .24, 3.85],
  ]) {
    const rim = new THREE.Mesh(
      new THREE.TorusGeometry(radius, thickness, 6, economy ? 64 : 128, length),
      new THREE.MeshBasicMaterial({color, transparent: true, opacity: .78,
        blending: THREE.AdditiveBlending, depthWrite: false}),
    );
    rim.rotation.z = angle;
    scan.add(rim);
  }
  const tickValues = [];
  const tickColors = [];
  for (let i = 0; i < 100; i++) {
    const a = (i / 100) * Math.PI * 2;
    for (const r of [1.72, i % 5 === 0 ? 1.82 : 1.76]) {
      tickValues.push(Math.cos(a) * r, Math.sin(a) * r, 0);
      tickColors.push(
        ...color
          .clone()
          .multiplyScalar(i % 5 === 0 ? 1 : 0.35)
          .toArray(),
      );
    }
  }
  scan.add(
    new THREE.LineSegments(
      new THREE.BufferGeometry()
        .setAttribute(
          "position",
          new THREE.Float32BufferAttribute(tickValues, 3),
        )
        .setAttribute("color", new THREE.Float32BufferAttribute(tickColors, 3)),
      new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.65,
        blending: THREE.AdditiveBlending,
      }),
    ),
  );
  const orbit = new THREE.Group();
  root.add(orbit);
  for (let i = 0; i < 2; i++) {
    const curve = new THREE.EllipseCurve(
      0,
      0,
      1.95,
      1.58,
      0,
      Math.PI * 2,
      false,
      0,
    );
    const geo = new THREE.BufferGeometry().setFromPoints(
      curve.getPoints(220).map((p) => new THREE.Vector3(p.x, p.y, 0)),
    );
    const line = new THREE.Line(
      geo,
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.2 }),
    );
    line.rotation.set(0.8 + i * 0.7, 0.35 + i * 0.8, i * 0.4);
    orbit.add(line);
  }
  const beacons = new THREE.Group();
  root.add(beacons);
  for (let i = 0; i < 5; i++) {
    const node = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: texture,
        color: i % 2 ? pale : color,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    node.scale.setScalar(i === 0 ? 0.16 : 0.1);
    beacons.add(node);
  }
  const pulses = new THREE.Group();
  root.add(pulses);
  for (let i = 0; i < 3; i++) {
    const geo = new THREE.BufferGeometry().setFromPoints(
      Array.from({ length: 97 }, (_, j) => {
        const angle = (j / 96) * Math.PI * 2;
        return new THREE.Vector3(Math.cos(angle), Math.sin(angle), 0);
      }),
    );
    pulses.add(
      new THREE.Line(
        geo,
        new THREE.LineBasicMaterial({
          color: pale,
          transparent: true,
          opacity: 0,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        }),
      ),
    );
  }
  const radial = new THREE.LineSegments(
    new THREE.BufferGeometry().setAttribute(
      "position",
      new THREE.Float32BufferAttribute(new Float32Array(96 * 6), 3),
    ),
    new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.3,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  root.add(radial);
  const segments = new THREE.Group();
  root.add(segments);
  for (let i = 0; i < 8; i++) {
    const values = [];
    const radius = 1.15 + (i % 3) * 0.28;
    for (let j = 0; j < 65; j++) {
      const a = (j / 64) * (Math.PI * 0.6) + i;
      values.push(Math.cos(a) * radius, Math.sin(a) * radius, 0);
    }
    const arc = new THREE.Line(
      new THREE.BufferGeometry().setAttribute(
        "position",
        new THREE.Float32BufferAttribute(values, 3),
      ),
      new THREE.LineBasicMaterial({
        color: i % 2 ? color : pale,
        transparent: true,
        opacity: 0.3,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    arc.rotation.set(i * 0.47, i * 0.28, i * 0.39);
    segments.add(arc);
  }
  return {
    root,
    shell,
    rings,
    heart,
    scan,
    orbit,
    points,
    texture,
    beacons,
    pulses,
    radial,
    segments,
    energySurface,
  };
}

