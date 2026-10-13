import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const target = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../core/spatial');
const source = process.argv[2];
if (!source) throw Error('Provide the alpha12 source directory.');
const original = fs.readFileSync(path.join(source, 'src/components/Hologram.jsx'), 'utf8');
const start = original.indexOf('function seeded(seed)');
const end = original.indexOf('export default function Hologram');
if (start < 0 || end < start) throw Error('Unexpected original core structure.');
fs.mkdirSync(target, {recursive: true});
fs.writeFileSync(path.join(target, 'core-model.mjs'),
  'import * as THREE from "three";\nimport { energyMaterial } from "./shaders.mjs";\n' +
  'const PALETTE = {amber:"#ffae4e",cyan:"#5be8ff",paleAmber:"#ffe6a8",paleCyan:"#d0ffff"};\n' +
  original.slice(start, end));
for (const name of ['shaders.mjs', 'core-profiles.mjs']) {
  fs.copyFileSync(path.join(source, 'src/interface', name), path.join(target, name));
}
