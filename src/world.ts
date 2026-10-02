import * as THREE from 'three';
import { glslColor, toon } from './look';
import { districtOf, type District } from './districts';
import { instance, kit, landmarkModels, sag, wirePoints } from './scenery';
import { FacadeBuilder, facadeSets, houseSet, type FacadeImage } from './facades';

// The city is a 10x10 grid of blocks. Street centerlines sit every CELL units.
// SF-style hills: intersections are flat and the streets between them are
// straight slopes, so the car launches off every crest when driven fast.
export const CELL = 64;
export const N = 10;
export const HALF = (N * CELL) / 2;
export const STREET_HALF = 6; // 12 m curb to curb
export const SIDEWALK_EDGE = 9; // sidewalk runs from the curb to here; front yards beyond
export const BUILD_INSET = 12;
// Hills stay flat for 8 m around each intersection (the slopes were tuned with this).
const TERRAIN_FLAT = 8;
export const BOUND = HALF + 6;

export function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

// North is -z. The bay wraps the north and east edges; downtown is flat in the north-east.
const HILLS = [
  { x: 40, z: -170, h: 32, s: 68 }, // Nob Hill
  { x: -100, z: -255, h: 28, s: 58 }, // Russian Hill
  { x: -215, z: 190, h: 44, s: 82 }, // Twin Peaks
  { x: -205, z: -110, h: 24, s: 72 }, // Pacific Heights
  { x: 185, z: 225, h: 20, s: 55 }, // Potrero Hill
  { x: -40, z: 70, h: 12, s: 48 }, // Alamo Square
];

const corner = new Float32Array((N + 1) * (N + 1));
{
  const r = rng(11);
  for (let j = 0; j <= N; j++)
    for (let i = 0; i <= N; i++) {
      const x = -HALF + i * CELL;
      const z = -HALF + j * CELL;
      let h = 1.5;
      for (const k of HILLS) h += 1.3 * k.h * Math.exp(-((x - k.x) ** 2 + (z - k.z) ** 2) / (2 * k.s * k.s));
      h += (r() - 0.5) * 2.5;
      corner[j * (N + 1) + i] = Math.max(1, h);
    }
}

const FLAT = TERRAIN_FLAT / CELL;
const remap = (t: number) => clamp((t - FLAT) / (1 - 2 * FLAT), 0, 1);

export function heightAt(x: number, z: number): number {
  const fx = (clamp(x, -HALF, HALF) + HALF) / CELL;
  const fz = (clamp(z, -HALF, HALF) + HALF) / CELL;
  const i = Math.min(N - 1, Math.floor(fx));
  const j = Math.min(N - 1, Math.floor(fz));
  const u = remap(fx - i);
  const v = remap(fz - j);
  const a = corner[j * (N + 1) + i];
  const b = corner[j * (N + 1) + i + 1];
  const c = corner[(j + 1) * (N + 1) + i];
  const d = corner[(j + 1) * (N + 1) + i + 1];
  return (a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v;
}

// The bay: the city drops off its edges to a sandy sea floor you can drive on.
export const WATER = -2;
export const SEA_FLOOR = -14;
// East and north (the bay side) are open out to here; west and south stop at BOUND.
export const SEA_REACH = HALF + 170;

// The Palace of Fine Arts' lagoon (assets/blender/landmarks.py PF_LAGOON), in the park on
// block 0,0: the model's water sheet sits at `level`, half a metre below the bank; the bed
// is carved out of the terrain below it, so a cab can drive in.
const PALACE = { x: -HALF + CELL / 2, z: -HALF + CELL / 2 };
export const LAGOON = (() => {
  const x = PALACE.x + 10, z = PALACE.z + 1;
  return { x, z, rx: 8, rz: 13, level: heightAt(x, z) - 0.5 };
})();
const LAGOON_BANK = 1.6; // the carve reaches this far past the water's edge

// Alcatraz out in the bay (assets/blender/landmarks.py AZ_*): the model's origin, at the
// water line. features.ts gives it ground: the island's top, its cliffs and the causeway.
export const ALCATRAZ = { x: 150, z: -440, top: WATER + 7 };

// The surface of whatever water is here: the lagoon, or the bay.
export function waterAt(x: number, z: number) {
  const u = (x - LAGOON.x) / LAGOON.rx, v = (z - LAGOON.z) / LAGOON.rz;
  return u * u + v * v < 1 ? LAGOON.level : WATER;
}

export function terrainAt(x: number, z: number) {
  const over = Math.max(Math.abs(x), Math.abs(z)) - (HALF + 8);
  let h = heightAt(x, z);
  const u = (x - LAGOON.x) / (LAGOON.rx + LAGOON_BANK), v = (z - LAGOON.z) / (LAGOON.rz + LAGOON_BANK);
  const s = u * u + v * v;
  if (s < 1) {
    const t = clamp((1 - s) / 0.28, 0, 1);
    h += (LAGOON.level - 1.4 - h) * t * t * (3 - 2 * t);
  }
  if (over <= 0) return h;
  const t = clamp(over / 24, 0, 1);
  return h + (SEA_FLOOR - h) * t * t * (3 - 2 * t);
}

// Extra round obstacles outside the city blocks (bridge towers, seabed rocks).
export const extraCircles: Circle[] = [];
const renderHeight = terrainAt;

export type BlockKind = 'res' | 'downtown' | 'park' | 'ladies' | 'landmark';
export interface Circle { x: number; z: number; r: number; breakable?: boolean; down?: boolean }

// Trees knock over when hit hard enough. collide() queues them here; the game animates them.
export const TREE_BREAK_SPEED = 7; // m/s (about 16 mph); slower than this, a tree is solid
export const brokenTrees: Circle[] = [];
// Anything that topples when hit (trees, lamps, poles). locals: each instanced part's offset within the model.
export interface TreeRef { circle: Circle; base: THREE.Matrix4; meshes: THREE.InstancedMesh[]; locals: THREE.Matrix4[]; index: number; kind: 'tree' | 'lamp' | 'pole' }
export const treeRefs = new Map<Circle, TreeRef>();
type Species = 'plane' | 'cypress' | 'palm';
type TreeSpot = { m: THREE.Matrix4; c: Circle; species: Species };
export interface Block {
  bi: number;
  bj: number;
  kind: BlockKind;
  x0: number; x1: number; z0: number; z1: number; // building footprint
  solid: boolean;
  circles: Circle[];
}

// 0,0 is the Palace of Fine Arts' park; 5,4 is City Hall.
const PARKS = new Set(['4,5', '2,7', '0,2', '0,3', '3,0', '1,8', '0,0']);
const LANDMARK_BLOCKS = new Set(['8,2', '7,1', '9,1', '5,4']);

export const blocks: Block[] = [];
{
  const r = rng(23);
  for (let bj = 0; bj < N; bj++)
    for (let bi = 0; bi < N; bi++) {
      const key = `${bi},${bj}`;
      let kind: BlockKind = 'res';
      if (PARKS.has(key)) kind = 'park';
      else if (LANDMARK_BLOCKS.has(key)) kind = 'landmark';
      else if (key === '5,5') kind = 'ladies';
      else if (districtOf(bi, bj).id === 'fidi') kind = 'downtown';
      const cx = -HALF + bi * CELL;
      const cz = -HALF + bj * CELL;
      blocks.push({
        bi, bj, kind,
        x0: cx + BUILD_INSET, x1: cx + CELL - BUILD_INSET,
        z0: cz + BUILD_INSET, z1: cz + CELL - BUILD_INSET,
        solid: kind !== 'park',
        circles: [],
      });
    }
}

export function blockAt(x: number, z: number): Block | null {
  const bi = Math.floor((x + HALF) / CELL);
  const bj = Math.floor((z + HALF) / CELL);
  if (bi < 0 || bj < 0 || bi >= N || bj >= N) return null;
  return blocks[bj * N + bi];
}

// Push a circle of radius r out of buildings, trees and the sea wall.
// Returns the impact speed (velocity into the obstacle before the bounce).
export function collide(pos: THREE.Vector3, vel: THREE.Vector2, r: number): number {
  let impact = 0;
  const hit = (nx: number, nz: number) => {
    const vn = vel.x * nx + vel.y * nz;
    if (vn < 0) {
      impact = Math.max(impact, -vn);
      vel.x -= nx * vn * 1.35;
      vel.y -= nz * vn * 1.35;
      if (-vn > 8) vel.multiplyScalar(0.8);
    }
  };
  const b = blockAt(pos.x, pos.z);
  if (b) {
    if (b.solid) {
      const ex0 = b.x0 - r, ex1 = b.x1 + r, ez0 = b.z0 - r, ez1 = b.z1 + r;
      if (pos.x > ex0 && pos.x < ex1 && pos.z > ez0 && pos.z < ez1) {
        const pl = pos.x - ex0, pr = ex1 - pos.x, pt = pos.z - ez0, pb = ez1 - pos.z;
        const m = Math.min(pl, pr, pt, pb);
        if (m === pl) { pos.x = ex0; hit(-1, 0); }
        else if (m === pr) { pos.x = ex1; hit(1, 0); }
        else if (m === pt) { pos.z = ez0; hit(0, -1); }
        else { pos.z = ez1; hit(0, 1); }
      }
    }
    for (const c of b.circles) {
      if (c.down) continue;
      const dx = pos.x - c.x, dz = pos.z - c.z;
      const d = Math.hypot(dx, dz);
      if (d < c.r + r && d > 1e-4) {
        if (c.breakable && vel.length() > TREE_BREAK_SPEED) {
          c.down = true;
          brokenTrees.push(c);
          vel.multiplyScalar(0.85);
          continue;
        }
        const nx = dx / d, nz = dz / d;
        pos.x = c.x + nx * (c.r + r);
        pos.z = c.z + nz * (c.r + r);
        hit(nx, nz);
      }
    }
  }
  if (Math.abs(pos.x) > HALF + 10 || Math.abs(pos.z) > HALF + 10) {
    for (const c of extraCircles) {
      const dx = pos.x - c.x, dz = pos.z - c.z;
      const d = Math.hypot(dx, dz);
      if (d < c.r + r && d > 1e-4) {
        const nx = dx / d, nz = dz / d;
        pos.x = c.x + nx * (c.r + r);
        pos.z = c.z + nz * (c.r + r);
        hit(nx, nz);
      }
    }
  }
  // West and south end at a sea wall; the bay to the east and north is open.
  const lim = BOUND - r, reach = SEA_REACH - r;
  if (pos.x > reach) { pos.x = reach; hit(-1, 0); }
  if (pos.x < -lim) { pos.x = -lim; hit(1, 0); }
  if (pos.z > lim) { pos.z = lim; hit(0, -1); }
  if (pos.z < -reach) { pos.z = -reach; hit(0, 1); }
  return impact;
}

export type Side = 'N' | 'S' | 'E' | 'W';
export interface Curb {
  walk: THREE.Vector3; // where a person stands on the sidewalk
  road: THREE.Vector3; // centre of the pickup / drop zone, in the lane
  facing: number; // yaw for a person looking at the street
}

// Distances from the street centreline: where people stand, and the lane beside them.
export const CURB_WALK = 7.5;
export const CURB_ROAD = 3;

// A point on the curb of block (bi, bj). t runs 0..1 along that side.
export function curb(bi: number, bj: number, side: Side, t: number): Curb {
  const cx = -HALF + bi * CELL;
  const cz = -HALF + bj * CELL;
  const along = BUILD_INSET + 4 + t * (CELL - 2 * BUILD_INSET - 8);
  let wx = 0, wz = 0, rx = 0, rz = 0, facing = 0;
  if (side === 'N') { wx = rx = cx + along; wz = cz + CURB_WALK; rz = cz + CURB_ROAD; facing = Math.PI; }
  if (side === 'S') { wx = rx = cx + along; wz = cz + CELL - CURB_WALK; rz = cz + CELL - CURB_ROAD; facing = 0; }
  if (side === 'W') { wz = rz = cz + along; wx = cx + CURB_WALK; rx = cx + CURB_ROAD; facing = -Math.PI / 2; }
  if (side === 'E') { wz = rz = cz + along; wx = cx + CELL - CURB_WALK; rx = cx + CELL - CURB_ROAD; facing = Math.PI / 2; }
  return {
    walk: new THREE.Vector3(wx, heightAt(wx, wz), wz),
    road: new THREE.Vector3(rx, heightAt(rx, rz), rz),
    facing,
  };
}

export interface Landmark { name: string; curb: Curb }
const LANDMARK_SPOTS: [string, number, number, Side, number][] = [
  ['Salesfarce Tower', 8, 2, 'S', 0.5],
  ['The Pyramid', 7, 1, 'W', 0.5],
  ['Ferry Building', 9, 1, 'S', 0.3],
  ['Painted Ladies', 5, 5, 'W', 0.5],
  ['Coit Tower', 3, 0, 'S', 0.5],
  ['Dolores Park', 2, 7, 'N', 0.5],
  ['Phlz Coffee', 5, 3, 'N', 0.3],
  ["Barri's Bootcamp", 6, 6, 'E', 0.6],
  ['Series A Lounge', 7, 3, 'S', 0.7],
  ['Sand Hill On-Ramp', 5, 9, 'S', 0.5],
  ['Twin Peaks Lookout', 1, 7, 'N', 0.5],
  ['The Lab', 6, 4, 'E', 0.4],
  ['Crypto Castle', 8, 6, 'N', 0.5],
  ['Burrito Spot', 3, 6, 'E', 0.5],
  ['City Hall', 5, 4, 'E', 0.5],
  ['Dragon Gate', 7, 2, 'W', 0.75], // on Grant Ave just south of the gate, which spans the street
  ['Palace of Fine Arts', 0, 0, 'E', 0.5], // across the sidewalk from the lagoon
  ['Lombard Street', 2, 0, 'S', 0.1], // the foot of the crooked street
];
// One-of-a-kind buildings, painted from their own drawing (public/facades/drop-*.jpg),
// so every drop-off is recognisable without a sign. [drawing, block bi, bj, face, t, width]
// t places the lot's centre along the face, as for curb().
const SPECIAL_LOTS: [string, number, number, Side, number, number][] = [
  ['drop-phlz', 5, 3, 'N', 0.3, 14],
  ['drop-barris', 6, 6, 'E', 0.6, 16],
  ['drop-lab', 6, 4, 'E', 0.4, 16],
  ['drop-crypto', 8, 6, 'N', 0.5, 18],
  ['drop-burrito', 3, 6, 'E', 0.5, 16],
  ['drop-ladies-b', 5, 5, 'W', 0.5, 16], // Postcard Row, facing Alamo Square
  ['drop-ladies-a', 5, 5, 'N', 0.42, 21], // one lot in, so a painted corner house turns the corner
];
// Drawings for the base of a downtown tower: [drawing, block bi, bj, face, t].
const SPECIAL_BASES: [string, number, number, Side, number][] = [
  ['drop-seriesa', 7, 3, 'S', 0.7],
];
// Where along a face (world x for N/S, world z for W/E) a curb t falls.
const alongFace = (bi: number, bj: number, side: Side, t: number) =>
  (side === 'N' || side === 'S' ? -HALF + bi * CELL : -HALF + bj * CELL) + BUILD_INSET + 4 + t * (CELL - 2 * BUILD_INSET - 8);
const dropImage = (id: string) => (facadeSets.drops ?? []).find((f) => f.id === id);

export const landmarks: Landmark[] = LANDMARK_SPOTS.map(([name, bi, bj, side, t]) => ({
  name,
  curb: curb(bi, bj, side, t),
}));
// Alcatraz has no curb: the drop-off is on the landing, up the causeway from the sea floor.
landmarks.push({
  name: 'Alcatraz',
  curb: {
    walk: new THREE.Vector3(ALCATRAZ.x + 8, ALCATRAZ.top, ALCATRAZ.z - 4.5),
    road: new THREE.Vector3(ALCATRAZ.x + 9, ALCATRAZ.top, ALCATRAZ.z),
    facing: 0,
  },
});

// Builds every static mesh: ground, buildings, landmarks, trees, water, signs.
export function buildWorld(scene: THREE.Scene) {
  scene.add(makeTerrain());
  scene.add(makeSeaWall());

  const water = new THREE.Mesh(
    new THREE.PlaneGeometry(4000, 4000),
    toon({ color: 0x2f86b0, transparent: true, opacity: 0.55, depthWrite: false }),
  );
  water.rotation.x = -Math.PI / 2;
  water.position.y = WATER;
  water.renderOrder = 2;
  scene.add(water);
  scene.add(makeSeabed());

  // style: 0 = house windows, 1 = glass tower bands, 2 = plain trim (cornices, doors, awnings)
  const boxes: { x: number; y: number; z: number; sx: number; sy: number; sz: number; c: THREE.Color; ground: number; top: number; style: number }[] = [];
  const addBox = (x0: number, x1: number, z0: number, z1: number, height: number, color: THREE.ColorRepresentation, tower = false, styleOverride?: number) => {
    const style = styleOverride ?? (tower ? 1 : 0);
    const hs = [heightAt(x0, z0), heightAt(x1, z0), heightAt(x0, z1), heightAt(x1, z1)];
    const ground = Math.min(...hs);
    const base = ground - 2;
    const top = Math.max(...hs) + height;
    boxes.push({
      x: (x0 + x1) / 2, y: (base + top) / 2, z: (z0 + z1) / 2,
      sx: x1 - x0, sy: top - base, sz: z1 - z0, c: new THREE.Color(color), ground, top, style,
    });
    return top;
  };
  // A box at an exact height range (bay windows, cornices, doors, awnings).
  const addPart = (x0: number, x1: number, z0: number, z1: number, y0: number, y1: number, color: THREE.ColorRepresentation, style: number, ground = y0) => {
    boxes.push({ x: (x0 + x1) / 2, y: (y0 + y1) / 2, z: (z0 + z1) / 2, sx: x1 - x0, sy: y1 - y0, sz: z1 - z0, c: new THREE.Color(color), ground, top: y1, style });
  };
  // Street-facing house walls, some of which get a graffiti tag.
  const walls: { x: number; z: number; nx: number; nz: number }[] = [];

  const r = rng(99);
  // San Francisco on a sunny day: butter, mint, dusty blue, cream, terracotta, sage, peach.
  // Slightly muted so the (saturated) people stand out against them.
  const mute = (c: number) => new THREE.Color(c).lerp(new THREE.Color(0xc9c2b6), 0.22).getHex();
  const PASTEL = [0xf3dc8a, 0xb7dcc4, 0x9fbad3, 0xf2e6cc, 0xd98a6c, 0xb3c79c, 0xf0c4a2, 0xe9e3d6, 0xc7b8d8].map(mute);
  const LADIES = [0x5f9ec2, 0xe58fa5, 0xf2cf55, 0x86c07a, 0xb08ad8, 0xee8f5a].map(mute);
  const GLASS = [0xc9d3dc, 0xb8c4cf, 0xd9d2c3, 0x9fb0c0, 0xe2ddd2, 0xaebdca];
  const trees: TreeSpot[] = [];
  const streetTrees: TreeSpot[] = [];
  const gables: { m: THREE.Matrix4; c: THREE.Color }[] = [];
  const facades = new FacadeBuilder();

  for (const b of blocks) {
    const { x0, x1, z0, z1 } = b;
    if (b.kind === 'park') {
      const count = 9;
      for (let k = 0; k < count; k++) {
        const tx = x0 + 3 + r() * (x1 - x0 - 6);
        const tz = z0 + 3 + r() * (z1 - z0 - 6);
        if (b.bi === 3 && b.bj === 0 && Math.hypot(tx - (x0 + x1) / 2, tz - (z0 + z1) / 2) < 9) continue;
        if (b.bi === 0 && b.bj === 0 && Math.hypot(tx - PALACE.x + 1, tz - PALACE.z) < 22) continue; // the Palace and its lagoon
        const circle: Circle = { x: tx, z: tz, r: 1.1, breakable: true };
        b.circles.push(circle);
        const s = 0.8 + r() * 0.6;
        // Palms in Dolores Park, cypresses and plane trees elsewhere.
        const species: Species = b.bi === 2 && b.bj === 7 ? 'palm' : r() < 0.35 ? 'cypress' : 'plane';
        trees.push({ species, c: circle, m: new THREE.Matrix4().compose(
          new THREE.Vector3(tx, heightAt(tx, tz), tz),
          new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), r() * 6),
          new THREE.Vector3(s, s, s),
        ) });
      }
      continue;
    }
    if (b.kind === 'downtown') {
      const tiles = (facadeSets.fidi ?? []).filter((f) => f.kind === 'tile');
      const bases = (facadeSets.fidi ?? []).filter((f) => f.kind === 'towerbase');
      const tower = (a0: number, a1: number, c0: number, c1: number, height: number) => {
        const tile = tiles.length ? tiles[Math.floor(r() * tiles.length)] : null;
        const top = addBox(a0, a1, c0, c1, height, tile ? tile.wall : GLASS[Math.floor(r() * GLASS.length)], true, tile ? 2 : undefined);
        if (!tile) return;
        const randomBase = bases.length ? bases[Math.floor(r() * bases.length)] : null;
        // Paint all four sides: the tile repeats every 4 floors (14.4 m), with a lobby at street level.
        for (const [cx, cz, fnx, fnz, w, face] of [[(a0 + a1) / 2, c0, 0, -1, a1 - a0, 'N'], [(a0 + a1) / 2, c1, 0, 1, a1 - a0, 'S'], [a0, (c0 + c1) / 2, -1, 0, c1 - c0, 'W'], [a1, (c0 + c1) / 2, 1, 0, c1 - c0, 'E']] as const) {
          // A landmark lobby replaces the usual one on the face (and tower) it stands on.
          const spec = SPECIAL_BASES.find(([id, bi, bj, f, t]) => {
            if (bi !== b.bi || bj !== b.bj || f !== face || !dropImage(id)) return false;
            const at = alongFace(bi, bj, f, t), onEdge = f === 'N' ? c0 === z0 : f === 'S' ? c1 === z1 : f === 'W' ? a0 === x0 : a1 === x1;
            return onEdge && (f === 'N' || f === 'S' ? at > a0 && at < a1 : at > c0 && at < c1);
          });
          const base = spec ? dropImage(spec[0])! : randomBase;
          const g = heightAt(cx, cz) - 1;
          const y0 = base ? g + 8.5 : g;
          facades.add({ image: tile.id, cx, cz, nx: fnx, nz: fnz, width: w + 0.02, y0, y1: top, repeatU: Math.max(1, Math.round(w / 14.4)), repeatV: (top - y0) / 14.4 });
          const lobby = { nx: fnx, nz: fnz, y0: g - 1.5, y1: y0 + 0.05, lift: 0.05 };
          // Ordinary lobbies repeat along the face; a landmark gets 15 m of its own, centred on the drop-off.
          const rx = fnz, rz = -fnx; // along the face, left to right
          const paintBase = (img: FacadeImage, from: number, to: number) => {
            if (to - from < 0.5) return;
            const m = (from + to) / 2;
            facades.add({ ...lobby, image: img.id, cx: cx + rx * m, cz: cz + rz * m, width: to - from + 0.02, repeatU: img === base && spec ? 1 : Math.max(1, Math.round((to - from) / 15)) });
          };
          if (spec && base) {
            const at = alongFace(b.bi, b.bj, face, spec[4]) - (face === 'N' || face === 'S' ? cx : cz);
            const off = (face === 'N' || face === 'S' ? rx : rz) * at; // signed offset along the right vector
            const c = clamp(off, -w / 2 + 7.5, w / 2 - 7.5);
            paintBase(base, c - 7.5, c + 7.5);
            if (randomBase) { paintBase(randomBase, -w / 2, c - 7.5); paintBase(randomBase, c + 7.5, w / 2); }
          } else if (base) paintBase(base, -w / 2, w / 2);
        }
      };
      const split = r() < 0.5;
      if (split) {
        const mx = (x0 + x1) / 2, mz = (z0 + z1) / 2;
        for (const [a0, a1, c0, c1] of [[x0, mx - 1, z0, mz - 1], [mx + 1, x1, z0, mz - 1], [x0, mx - 1, mz + 1, z1], [mx + 1, x1, mz + 1, z1]])
          tower(a0, a1, c0, c1, 24 + r() * 50);
      } else {
        tower(x0, x1, z0, z1, 40 + r() * 70);
      }
      continue;
    }
    if (b.kind === 'landmark') continue;
    const dist = districtOf(b.bi, b.bj);
    const ladies = b.kind === 'ladies';
    buildFrontages(b, ladies ? PAINTED_LADIES : dist, ladies ? LADIES : dist.colors, r, addBox, addPart, gables, walls, facades, ladies ? 'haight' : dist.id);
    addStreetTrees(b, r, streetTrees);
  }

  const geo = new THREE.BoxGeometry(1, 1, 1);
  geo.setAttribute('aGround', new THREE.InstancedBufferAttribute(new Float32Array(boxes.map((b) => b.ground)), 1));
  geo.setAttribute('aTop', new THREE.InstancedBufferAttribute(new Float32Array(boxes.map((b) => b.top)), 1));
  geo.setAttribute('aTower', new THREE.InstancedBufferAttribute(new Float32Array(boxes.map((b) => b.style)), 1));
  const inst = new THREE.InstancedMesh(geo, buildingMaterial(), boxes.length);
  const m = new THREE.Matrix4();
  boxes.forEach((bx, i) => {
    m.makeScale(bx.sx, bx.sy, bx.sz).setPosition(bx.x, bx.y, bx.z);
    inst.setMatrixAt(i, m);
    inst.setColorAt(i, bx.c);
  });
  addGraffiti(scene, walls, r);
  inst.castShadow = true;
  inst.receiveShadow = true;
  scene.add(inst);
  scene.add(makeGables(gables));
  scene.add(facades.build());

  scene.add(makeTrees(trees));
  scene.add(makeTrees(streetTrees));
  buildStreetFurniture(scene, streetTrees);
  addLandmarks(scene);
  addGoldenGate(scene);

}

// Windows, frames and a white cornice painted per pixel, so houses read as
// Victorians and towers as glass without any extra geometry.
function buildingMaterial() {
  const mat = toon();
  const decl = 'varying vec3 vBPos;\nvarying vec3 vBNormal;\nvarying float vGround;\nvarying float vTop;\nvarying float vTower;\n';
  mat.onBeforeCompile = (sh) => {
    sh.vertexShader = 'attribute float aGround;\nattribute float aTop;\nattribute float aTower;\n' + decl + sh.vertexShader.replace(
      '#include <begin_vertex>',
      `#include <begin_vertex>
      vec4 bw = vec4(transformed, 1.0);
      mat3 nm = mat3(modelMatrix);
      #ifdef USE_INSTANCING
        bw = instanceMatrix * bw;
        nm = nm * mat3(instanceMatrix);
      #endif
      vBPos = (modelMatrix * bw).xyz;
      vBNormal = normalize(nm * objectNormal);
      vGround = aGround; vTop = aTop; vTower = aTower;`,
    );
    sh.fragmentShader = decl + sh.fragmentShader.replace(
      '#include <color_fragment>',
      `#include <color_fragment>
      if (vBNormal.y > 0.6) {
        diffuseColor.rgb *= 0.8;
      } else {
        float along = abs(vBNormal.x) > 0.5 ? vBPos.z : vBPos.x;
        float y = vBPos.y - vGround;
        if (vTower > 1.5) {
          // plain trim: no windows
        } else if (vBPos.y > vTop - 0.8) {
          diffuseColor.rgb = ${glslColor(0xf6f1e6)};
        } else if (vTower > 0.5) {
          float band = step(0.4, fract(y / 3.6)) * step(0.1, fract(along / 3.0));
          diffuseColor.rgb = mix(diffuseColor.rgb, ${glslColor(0x56738f)}, band * 0.85);
        } else {
          // Tall, narrow sash windows, like a Victorian, not an office block.
          float fy = fract(y / 3.6), fa = fract(along / 2.8);
          float lift = step(1.4, y);
          float frame = step(0.14, fy) * step(fy, 0.9) * step(0.27, fa) * step(fa, 0.73) * lift;
          float win = step(0.2, fy) * step(fy, 0.84) * step(0.33, fa) * step(fa, 0.67) * lift;
          diffuseColor.rgb = mix(diffuseColor.rgb, ${glslColor(0xf6f1e6)}, frame);
          diffuseColor.rgb = mix(diffuseColor.rgb, ${glslColor(0x3d4a5c)}, win);
        }
      }`,
    );
  };
  return mat;
}

// A few spray-painted tags, used sparingly.
const TAGS = ['CLANK', 'BEEP', 'NO ROBOTS', 'HUMAN MADE', 'CONE ZONE', 'FSD?', 'R.I.P. CRUISE', 'OBEY THE LIDAR'];
const TAG_COLORS = ['#e2483b', '#26232b', '#3f6fd6', '#f3c530', '#2f9a6a', '#f4f1e8'];

function tagTexture(text: string, color: string, tilt: number) {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 256;
  const g = c.getContext('2d')!;
  g.translate(256, 128);
  g.rotate(tilt);
  g.font = `900 ${text.length > 8 ? 64 : 92}px Impact, "Arial Black", sans-serif`;
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.lineJoin = 'round';
  g.lineWidth = 16;
  g.strokeStyle = color === '#26232b' ? '#f4f1e8' : '#1b1722';
  g.strokeText(text, 0, 0);
  g.fillStyle = color;
  g.fillText(text, 0, 0);
  // Drips.
  const w = g.measureText(text).width;
  for (let k = 0; k < 5; k++) {
    const x = -w / 2 + ((k + 0.5) / 5) * w;
    g.fillRect(x, 20, 5, 18 + ((k * 37) % 40));
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function addGraffiti(scene: THREE.Scene, walls: { x: number; z: number; nx: number; nz: number }[], r: () => number) {
  const mats = TAGS.map((t, i) => toon({
    map: tagTexture(t, TAG_COLORS[i % TAG_COLORS.length], (r() - 0.6) * 0.25),
    transparent: true,
    alphaTest: 0.4,
    polygonOffset: true,
    polygonOffsetFactor: -2,
  }));
  const geo = new THREE.PlaneGeometry(4, 2);
  const count = 26;
  for (let k = 0; k < count && walls.length; k++) {
    const w = walls.splice(Math.floor(r() * walls.length), 1)[0];
    const x = w.x + w.nx * 0.08, z = w.z + w.nz * 0.08;
    const mesh = new THREE.Mesh(geo, mats[Math.floor(r() * mats.length)]);
    mesh.position.set(x, heightAt(x + w.nx * 3, z + w.nz * 3) + 1.4 + r() * 0.8, z);
    mesh.rotation.y = Math.atan2(w.nx, w.nz);
    scene.add(mesh);
  }
}

const PAINTED_LADIES: District = { ...districtOf(4, 5), bays: 1, gables: 1, garages: 0.3, cornerFloors: 0, shops: 0, graffiti: 0 };
const AWNINGS = [0xd23b2e, 0x2f6b4f, 0x2d4a7a, 0xe8a33d, 0x7a3f8a];
const TRIM = 0xf6f1e6;

type AddBox = (x0: number, x1: number, z0: number, z1: number, height: number, color: THREE.ColorRepresentation, tower?: boolean, style?: number) => number;
type AddPart = (x0: number, x1: number, z0: number, z1: number, y0: number, y1: number, color: THREE.ColorRepresentation, style: number, ground?: number) => void;

// Row houses along each side of a block: narrow lots, flush to the sidewalk, with
// bay windows, cornices or gables, garage doors or stoops, and shops on the corners.
function buildFrontages(
  b: Block, d: District, colors: number[], r: () => number,
  addBox: AddBox, addPart: AddPart,
  gables: { m: THREE.Matrix4; c: THREE.Color }[],
  walls: { x: number; z: number; nx: number; nz: number }[],
  facades?: FacadeBuilder,
  districtId = '',
) {
  const { x0, x1, z0, z1 } = b;
  // Every house whose district has drawings gets a painted front.
  const set = facades ? houseSet(districtId) : [];
  const painted = set.length >= 3; // fewer and the street repeats itself
  let lastPick = -1;
  const DEPTH = 12;
  // side: [length start, length end, which face, outward normal]
  const rows: { a0: number; a1: number; face: 'N' | 'S' | 'W' | 'E'; corners: boolean }[] = [
    { a0: x0, a1: x1, face: 'N', corners: true },
    { a0: x0, a1: x1, face: 'S', corners: true },
    { a0: z0 + DEPTH, a1: z1 - DEPTH, face: 'W', corners: false },
    { a0: z0 + DEPTH, a1: z1 - DEPTH, face: 'E', corners: false },
  ];
  for (const row of rows) {
    // Split the frontage into lots, keeping room for a one-of-a-kind building.
    const special = facades ? SPECIAL_LOTS.find(([id, bi, bj, face]) => bi === b.bi && bj === b.bj && face === row.face && dropImage(id)) : undefined;
    let s0 = row.a1, s1 = row.a1;
    if (special) {
      const width = Math.min(special[5], row.a1 - row.a0);
      s0 = clamp(alongFace(b.bi, b.bj, row.face, special[4]) - width / 2, row.a0, row.a1 - width);
      s1 = s0 + width;
      if (s0 - row.a0 < 3) s0 = row.a0; // no slivers
      if (row.a1 - s1 < 3) s1 = row.a1;
    }
    const lots: [number, number][] = [];
    const split = (from: number, to: number) => {
      let a = from;
      while (to - a > 0.5) {
        let w = d.lot[0] + r() * (d.lot[1] - d.lot[0]);
        if (to - a - w < d.lot[0] * 0.75) w = to - a;
        lots.push([a, a + w]);
        a += w;
      }
    };
    split(row.a0, s0);
    const specialIndex = lots.length;
    if (special) lots.push([s0, s1]);
    split(s1, row.a1);
    lots.forEach(([la0, la1], i) => {
      const corner = row.corners && (i === 0 || i === lots.length - 1);
      // Local frame → world box. along: la0..la1; depth: 0 at the face, positive inward.
      const box = (p0: number, p1: number, d0: number, d1: number): [number, number, number, number] => {
        if (row.face === 'N') return [p0, p1, z0 + d0, z0 + d1];
        if (row.face === 'S') return [p0, p1, z1 - d1, z1 - d0];
        if (row.face === 'W') return [x0 + d0, x0 + d1, p0, p1];
        return [x1 - d1, x1 - d0, p0, p1];
      };
      const nx = row.face === 'W' ? -1 : row.face === 'E' ? 1 : 0;
      const nz = row.face === 'N' ? -1 : row.face === 'S' ? 1 : 0;
      const mid = (la0 + la1) / 2;
      const [fx0, fx1, fz0, fz1] = box(mid, mid, 0, 0);
      // Ground height at the facade, at a point along the lot (features sit on their own patch of slope).
      const groundAtLot = (p: number) => { const [ax0, ax1, az0, az1] = box(p, p, 0, 0); return heightAt((ax0 + ax1) / 2, (az0 + az1) / 2); };
      const front = groundAtLot(mid);
      const floors = Math.round(d.floors[0] + r() * (d.floors[1] - d.floors[0])) + (corner ? d.cornerFloors : 0);
      const color = colors[Math.floor(r() * colors.length)];
      const width = la1 - la0;
      if (special && i === specialIndex && facades) {
        // The landmark lot: as tall as its drawing, which keeps its proportions.
        const img = dropImage(special[0])!;
        const g0 = groundAtLot(la0), g1 = groundAtLot(la1), hi = Math.max(g0, g1), lo = Math.min(g0, g1);
        const [bx0, bx1, bz0, bz1] = box(la0, la1, 0, DEPTH);
        const maxGround = Math.max(heightAt(bx0, bz0), heightAt(bx1, bz0), heightAt(bx0, bz1), heightAt(bx1, bz1));
        const top = addBox(bx0, bx1, bz0, bz1, hi + width / 1.5 - maxGround, img.wall, false, 2);
        facades.add({ image: img.id, cx: (fx0 + fx1) / 2, cz: (fz0 + fz1) / 2, nx, nz, width: width + 0.02, y0: hi, y1: top });
        facades.addColour(img.base, { cx: (fx0 + fx1) / 2, cz: (fz0 + fz1) / 2, nx, nz, width: width + 0.02, y0: lo - 0.6, y1: hi });
        return;
      }
      if (painted && facades) {
        // Painted lot: a full-width box in the drawing's body colour; the drawing carries
        // the bays, doors and cornice. Neighbours never repeat a drawing.
        let pick = Math.floor(r() * set.length);
        if (pick === lastPick) pick = (pick + 1) % set.length;
        lastPick = pick;
        const img = set[pick];
        const top = addBox(...box(la0, la1, 0, DEPTH), floors * 3.3 + 0.5, img.wall, false, 2);
        const paint = (cx: number, cz: number, fnx: number, fnz: number, w: number, g0: number, g1: number) => {
          const lo = Math.min(g0, g1), hi = Math.max(g0, g1);
          // Start the drawing at the uphill end so nothing is buried; a foundation band fills below.
          facades.add({ image: img.id, cx, cz, nx: fnx, nz: fnz, width: w, y0: hi, y1: top });
          facades.addColour(img.base, { cx, cz, nx: fnx, nz: fnz, width: w, y0: lo - 0.6, y1: hi });
        };
        paint((fx0 + fx1) / 2, (fz0 + fz1) / 2, nx, nz, width + 0.02, groundAtLot(la0), groundAtLot(la1));
        if (corner) {
          // A corner lot also shows its side wall to the cross street: paint it as two narrow fronts.
          const end = i === 0 ? la0 : la1;
          const sx = (row.face === 'N' || row.face === 'S') ? (i === 0 ? -1 : 1) : 0;
          const sz = (row.face === 'W' || row.face === 'E') ? (i === 0 ? -1 : 1) : 0;
          for (const [k0, k1] of [[0, 0.5], [0.5, 1]]) {
            const [ax0, , az0] = box(end, end, k0 * DEPTH, k0 * DEPTH);
            const [bx0, , bz0] = box(end, end, k1 * DEPTH, k1 * DEPTH);
            paint((ax0 + bx0) / 2, (az0 + bz0) / 2, sx, sz, DEPTH / 2 + 0.02, heightAt(ax0, az0), heightAt(bx0, bz0));
          }
        }
        return;
      }
      const gabled = !corner && r() < d.gables;
      const top = addBox(...box(la0 + 0.15, la1 - 0.15, 0, DEPTH), floors * 3.3 + 0.5, color);
      const shop = corner && r() < d.shops;
      if (gabled) {
        // A prism along the lot's depth, peak over the middle of the facade.
        const along = row.face === 'N' || row.face === 'S';
        const [gx0, gx1, gz0, gz1] = box(la0 + 0.15, la1 - 0.15, 0, DEPTH);
        const m = new THREE.Matrix4().compose(
          new THREE.Vector3((gx0 + gx1) / 2, top, (gz0 + gz1) / 2),
          new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), along ? 0 : Math.PI / 2),
          new THREE.Vector3(width - 0.3, Math.min(4.2, width * 0.55), DEPTH),
        );
        gables.push({ m, c: new THREE.Color(color).multiplyScalar(0.92) });
      } else {
        addPart(...box(la0, la1, -0.45, 0.6), top - 0.6, top, TRIM, 2); // cornice
      }
      if (floors >= 2 && width > 5 && r() < d.bays) {
        const bw = Math.min(3.4, width * 0.5);
        const off = width > 8 ? (r() < 0.5 ? -1 : 1) * (width / 4) : 0;
        const bg = Math.max(groundAtLot(mid + off - bw / 2), groundAtLot(mid + off + bw / 2));
        addPart(...box(mid + off - bw / 2, mid + off + bw / 2, -0.8, 0), bg + 3.4, top - (gabled ? 0.1 : 0.7), color, 0, bg);
        addPart(...box(mid + off - bw / 2 - 0.1, mid + off + bw / 2 + 0.1, -0.9, 0), top - (gabled ? 0.4 : 1.0), top - (gabled ? 0.1 : 0.7), TRIM, 2);
      }
      if (shop) {
        const lo = Math.min(groundAtLot(la0), groundAtLot(la1)), hi = Math.max(groundAtLot(la0), groundAtLot(la1));
        addPart(...box(la0 + 0.3, la1 - 0.3, -0.08, 0), lo - 0.5, hi + 3, 0x2e3a46, 2);
        addPart(...box(la0 + 0.2, la1 - 0.2, -1.5, 0), hi + 3, hi + 3.35, AWNINGS[Math.floor(r() * AWNINGS.length)], 2);
      } else if (r() < d.garages) {
        const gx = mid + (width > 6 ? (r() < 0.5 ? -1 : 1) * (width / 2 - 1.8) : 0);
        const gg = Math.min(groundAtLot(gx - 1.3), groundAtLot(gx + 1.3));
        addPart(...box(gx - 1.3, gx + 1.3, -0.08, 0), gg - 0.5, gg + 2.4, r() < 0.5 ? 0xe9e6dc : 0x4a4f58, 2);
      } else {
        const sx = mid + (width > 6 ? (r() < 0.5 ? -1 : 1) * (width / 2 - 1.4) : 0);
        const sg = Math.min(groundAtLot(sx - 0.8), groundAtLot(sx + 0.8));
        addPart(...box(sx - 0.8, sx + 0.8, -1.6, 0), sg - 0.5, sg + 0.9, 0xd8d2c4, 2); // stoop
      }
      if (r() < d.graffiti) walls.push({ x: (fx0 + fx1) / 2, z: (fz0 + fz1) / 2, nx, nz });
    });
  }
}

// Street trees in sidewalk planters, near the curb.
function addStreetTrees(b: Block, r: () => number, out: TreeSpot[]) {
  const cx = -HALF + b.bi * CELL, cz = -HALF + b.bj * CELL;
  const at = 6.9; // from the street centreline: just inside the curb
  for (const side of ['N', 'S', 'W', 'E'] as const) {
    for (const t of [0.3, 0.7]) {
      if (r() < 0.25) continue;
      const along = BUILD_INSET + t * (CELL - 2 * BUILD_INSET);
      let x = 0, z = 0;
      if (side === 'N') { x = cx + along; z = cz + at; }
      if (side === 'S') { x = cx + along; z = cz + CELL - at; }
      if (side === 'W') { x = cx + at; z = cz + along; }
      if (side === 'E') { x = cx + CELL - at; z = cz + along; }
      if (landmarks.some((l) => Math.hypot(l.curb.walk.x - x, l.curb.walk.z - z) < 7)) continue;
      if (Math.hypot(x + 69, z + 28) < 16) continue; // keep the robotaxi rank (src/rank.ts) clear
      const circle: Circle = { x, z, r: 0.4, breakable: true };
      b.circles.push(circle);
      const s = 0.55 + r() * 0.15;
      out.push({ species: 'plane', c: circle, m: new THREE.Matrix4().compose(
        new THREE.Vector3(x, heightAt(x, z), z),
        new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), r() * 6),
        new THREE.Vector3(s, s * 1.1, s),
      ) });
    }
  }
}

function makeGables(list: { m: THREE.Matrix4; c: THREE.Color }[]) {
  const shape = new THREE.Shape();
  shape.moveTo(-0.5, 0);
  shape.lineTo(0.5, 0);
  shape.lineTo(0, 1);
  shape.closePath();
  const geo = new THREE.ExtrudeGeometry(shape, { depth: 1, bevelEnabled: false });
  geo.translate(0, 0, -0.5);
  const inst = new THREE.InstancedMesh(geo, toon(), Math.max(1, list.length));
  list.forEach((g, i) => { inst.setMatrixAt(i, g.m); inst.setColorAt(i, g.c); });
  inst.count = list.length;
  inst.castShadow = true;
  return inst;
}

// Road paint is drawn per pixel in the shader so edges stay crisp.
const SURFACE_GLSL = /* glsl */ `
uniform sampler2D uParks;
varying vec3 vWPos;
float swHash(vec2 q) { return fract(sin(dot(q, vec2(41.3, 289.1))) * 43758.5453); }
// Concrete slabs with scored joints, a pale curb with an ink line at the gutter, and
// brick paver bands downtown.
vec3 sidewalk(vec2 p, vec2 d, float e, bool brick) {
  const float SH = ${STREET_HALF.toFixed(1)}, SW = ${SIDEWALK_EDGE.toFixed(1)};
  float across = e - SH;
  if (across < 0.1) return ${glslColor(0x2a2630)}; // ink at the gutter
  if (across < 0.38) return across < 0.13 ? ${glslColor(0xa39d92)} : ${glslColor(0xe4ded2)}; // curb face, curb top
  bool corner = d.x < SW && d.y < SW;
  vec2 q = corner ? p : vec2(d.x < d.y ? p.y : p.x, across); // (along, across)
  vec3 base = ${glslColor(0xbcb4a5)};
  if (brick && !corner && across < 1.7) {
    // Running-bond red brick, like Market Street.
    vec2 b = vec2(q.x / 0.42, (across - 0.38) / 0.21);
    b.x += 0.5 * mod(floor(b.y), 2.0);
    vec2 f = fract(b);
    float mortar = step(f.x, 0.08) + step(f.y, 0.12);
    vec3 c = ${glslColor(0xa65640)} * (0.9 + 0.14 * swHash(floor(b)));
    return mix(c, ${glslColor(0x8a7f74)}, clamp(mortar, 0.0, 1.0));
  }
  vec2 slab = vec2(1.6, corner ? 1.6 : (SW - SH - 0.38) / 2.0);
  vec2 sq = corner ? q / slab : vec2(q.x / slab.x, (across - 0.38) / slab.y);
  vec2 f = fract(sq);
  float joint = step(f.x, 0.04) + (corner ? step(f.y, 0.04) : step(f.y, 0.05) * step(0.5, sq.y));
  base *= 0.95 + 0.07 * swHash(floor(sq));
  return mix(base, base * 0.68, clamp(joint, 0.0, 1.0));
}
vec3 surface(vec2 p) {
  const float HALF = ${HALF.toFixed(1)}, CELL = ${CELL.toFixed(1)}, SH = ${STREET_HALF.toFixed(1)}, SW = ${SIDEWALK_EDGE.toFixed(1)}, BI = ${BUILD_INSET.toFixed(1)};
  float m = max(abs(p.x), abs(p.y));
  if (m > HALF + 12.0) return ${glslColor(0xb8a888)};
  if (m > HALF + 8.0) return ${glslColor(0x8d8d86)};
  vec2 l = mod(p + HALF, CELL);
  vec2 d = min(l, CELL - l);
  bool inZ = d.x < SH, inX = d.y < SH;
  if (inZ || inX) {
    vec3 c = ${glslColor(0x3b3e44)};
    if (inZ && !inX && d.y < SH + 3.0 && mod(p.x, 2.0) < 1.0) c = ${glslColor(0xd9d6cc)};
    if (inX && !inZ && d.x < SH + 3.0 && mod(p.y, 2.0) < 1.0) c = ${glslColor(0xd9d6cc)};
    if (inZ && !inX && d.x < 0.22 && d.y > SH + 4.0 && mod(p.y, 8.0) < 3.5) c = ${glslColor(0xe8cf5a)};
    if (inX && !inZ && d.y < 0.22 && d.x > SH + 4.0 && mod(p.x, 8.0) < 3.5) c = ${glslColor(0xe8cf5a)};
    return c;
  }
  float e = min(d.x, d.y);
  vec2 cell = floor((p + HALF) / CELL);
  vec4 kind = texture(uParks, (cell + 0.5) / ${N.toFixed(1)});
  if (e < SW || (e < BI && kind.g > 0.5)) return sidewalk(p, d, e, kind.b > 0.5);
  vec3 grass = ${glslColor(0x6fa04f)} * (0.94 + 0.06 * sin(p.x * 0.7) * cos(p.y * 0.6));
  if (e < BI) return e < SW + 0.3 ? ${glslColor(0x8a8478)} : grass; // low wall, then the front yard
  if (kind.r > 0.5) return grass;
  return ${glslColor(0x7c7a72)};
}
`;

function makeTerrain() {
  const size = 2 * (HALF + 40);
  const segs = size / 2;
  const geo = new THREE.PlaneGeometry(size, size, segs, segs);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) pos.setY(i, renderHeight(pos.getX(i), pos.getZ(i)));
  geo.computeVertexNormals();

  const parks = new Uint8Array(N * N * 4);
  for (const b of blocks) {
    if (b.kind === 'park') parks[(b.bj * N + b.bi) * 4] = 255;
    if (b.kind !== 'park' && !districtOf(b.bi, b.bj).yard) parks[(b.bj * N + b.bi) * 4 + 1] = 255; // paved to the building line
    if (b.kind === 'downtown' || b.kind === 'landmark') parks[(b.bj * N + b.bi) * 4 + 2] = 255; // brick paver bands
  }
  const tex = new THREE.DataTexture(parks, N, N);
  tex.magFilter = tex.minFilter = THREE.NearestFilter;
  tex.needsUpdate = true;

  const mat = toon();
  mat.onBeforeCompile = (sh) => {
    sh.uniforms.uParks = { value: tex };
    sh.vertexShader = 'varying vec3 vWPos;\n' + sh.vertexShader.replace(
      '#include <begin_vertex>',
      '#include <begin_vertex>\nvWPos = (modelMatrix * vec4(transformed, 1.0)).xyz;',
    );
    sh.fragmentShader = SURFACE_GLSL + sh.fragmentShader.replace(
      '#include <color_fragment>',
      '#include <color_fragment>\ndiffuseColor.rgb *= surface(vWPos.xz);',
    );
  };
  const mesh = new THREE.Mesh(geo, mat);
  mesh.receiveShadow = true;
  return mesh;
}

function makeSeaWall() {
  const mats: THREE.Matrix4[] = [];
  const edge = BOUND + 0.6;
  for (let s = -edge; s < edge; s += 6) {
    const c = s + 3;
    for (const [x, z, rot] of [[c, edge, 0], [-edge, c, 1]] as const) {
      const h = heightAt(x, z);
      mats.push(new THREE.Matrix4().compose(
        new THREE.Vector3(x, h + 0.2, z),
        new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), rot * Math.PI / 2),
        new THREE.Vector3(6.1, 2.4, 1.2),
      ));
    }
  }
  const inst = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), toon({ color: 0xa4a39b }), mats.length);
  mats.forEach((mm, i) => inst.setMatrixAt(i, mm));
  inst.castShadow = true;
  return inst;
}

// Kit trees are full-size models; these factors map the old scale numbers onto them.
const SPECIES_SCALE: Record<Species, number> = { plane: 0.8, cypress: 0.75, palm: 0.95 };

function makeTrees(spots: TreeSpot[]) {
  const g = new THREE.Group();
  for (const species of ['plane', 'cypress', 'palm'] as Species[]) {
    const list = spots.filter((t) => t.species === species);
    if (!list.length) continue;
    const template = kit[`tree_${species}`];
    if (template) {
      const k = SPECIES_SCALE[species];
      const mats = list.map((t) => t.m.clone().multiply(new THREE.Matrix4().makeScale(k, k, k)));
      const { group, meshes, locals } = instance(template, mats);
      list.forEach((t, i) => treeRefs.set(t.c, { circle: t.c, base: mats[i], meshes, locals, index: i, kind: 'tree' }));
      g.add(group);
      continue;
    }
    // Fallback: the old low-poly trees.
    const trunkGeo = new THREE.CylinderGeometry(0.25, 0.35, 2.4, 6).translate(0, 1.2, 0);
    const topGeo = new THREE.IcosahedronGeometry(2.2, 0).translate(0, 3.6, 0);
    const trunks = new THREE.InstancedMesh(trunkGeo, toon({ color: 0x6b4a2f }), list.length);
    const tops = new THREE.InstancedMesh(topGeo, toon({ color: 0x4f8f45 }), list.length);
    const id = new THREE.Matrix4();
    list.forEach(({ m, c }, i) => {
      trunks.setMatrixAt(i, m);
      tops.setMatrixAt(i, m);
      treeRefs.set(c, { circle: c, base: m.clone(), meshes: [trunks, tops], locals: [id, id], index: i, kind: 'tree' });
    });
    trunks.frustumCulled = tops.frustumCulled = false;
    tops.castShadow = trunks.castShadow = true;
    g.add(trunks, tops);
  }
  return g;
}

// Street furniture: lamps on every block, utility poles and wires in the residential
// districts, Muni trolley lines with shelters, and planters under street trees.
const TROLLEY_LINES: { axis: 'x' | 'z'; line: number }[] = [{ axis: 'z', line: -128 }, { axis: 'x', line: 64 }];
const RESIDENTIAL = new Set(['haight', 'mission', 'sunset', 'potrero', 'northbeach', 'pacheights']);

function streetPoint(axis: 'x' | 'z', line: number, along: number, offset: number) {
  const x = axis === 'z' ? line + offset : along;
  const z = axis === 'z' ? along : line + offset;
  return new THREE.Vector3(x, heightAt(x, z), z);
}

function addSolid(p: THREE.Vector3, r: number): Circle | null {
  const b = blockAt(p.x, p.z);
  if (!b) return null;
  const c: Circle = { x: p.x, z: p.z, r, breakable: true };
  b.circles.push(c);
  return c;
}

function nearRankOrSign(p: THREE.Vector3) {
  if (Math.hypot(p.x + 69, p.z + 28) < 18) return true;
  return landmarks.some((l) => Math.hypot(l.curb.walk.x - p.x, l.curb.walk.z - p.z) < 6);
}

function buildStreetFurniture(scene: THREE.Scene, streetTrees: TreeSpot[]) {
  const yawFor = (axis: 'x' | 'z', side: number) => (axis === 'z' ? (side > 0 ? -Math.PI / 2 : Math.PI / 2) : side > 0 ? Math.PI : 0);
  const onTrolley = (axis: 'x' | 'z', line: number) => TROLLEY_LINES.some((t) => t.axis === axis && t.line === line);
  const lamps: { m: THREE.Matrix4; c: Circle | null }[] = [];
  const poles: { m: THREE.Matrix4; c: Circle | null }[] = [];
  const trolley: THREE.Matrix4[] = [];
  const shelters: THREE.Matrix4[] = [];
  const wires: number[] = [];
  const q = new THREE.Quaternion(), one = new THREE.Vector3(1, 1, 1), up = new THREE.Vector3(0, 1, 0);
  const utilWires = wirePoints('utility_pole'), trolleyWire = wirePoints('trolley_pole')[0];

  for (const axis of ['x', 'z'] as const)
    for (let k = 0; k <= N; k++) {
      const line = -HALF + k * CELL;
      const trolleyLine = onTrolley(axis, line);
      let lastPole: THREE.Vector3[] | null = null;
      let lastSpan: THREE.Vector3[] | null = null;
      for (let j = 0; j < N; j++) {
        const mid = -HALF + j * CELL + CELL / 2;
        // A lamp per block side, alternating sides; the arm reaches over the road.
        const lside = (j + k) % 2 ? 1 : -1;
        const lp = streetPoint(axis, line, mid + lside * 10, lside * (STREET_HALF + 0.6));
        if (!nearRankOrSign(lp)) lamps.push({ m: new THREE.Matrix4().compose(lp, q.setFromAxisAngle(up, yawFor(axis, lside)), one), c: addSolid(lp, 0.25) });

        if (trolleyLine) {
          // Trolley poles both sides every 32 m, span wires across and two contact wires along.
          for (const a of [mid - 16, mid + 16]) {
            const span: THREE.Vector3[] = [];
            for (const side of [-1, 1]) {
              const p = streetPoint(axis, line, a, side * (STREET_HALF + 0.5));
              if (nearRankOrSign(p)) continue;
              trolley.push(new THREE.Matrix4().compose(p, q.setFromAxisAngle(up, yawFor(axis, side)), one));
              addSolid(p, 0.3);
              span.push(p.clone().add(new THREE.Vector3(0, trolleyWire.y, 0)));
            }
            if (span.length === 2) {
              sag(span[0], span[1], wires, 0.15, 4);
              const contact = [-1.4, 1.4].map((o) => streetPoint(axis, line, a, o).add(new THREE.Vector3(0, trolleyWire.y - 0.5, 0)));
              if (lastSpan) for (let w = 0; w < 2; w++) sag(lastSpan[w], contact[w], wires, 0.25, 6);
              lastSpan = contact;
            }
          }
          if (j % 2 === 0) {
            const side = j % 4 === 0 ? 1 : -1;
            const p = streetPoint(axis, line, mid, side * (STREET_HALF + 2.3));
            if (!nearRankOrSign(p)) {
              shelters.push(new THREE.Matrix4().compose(p, q.setFromAxisAngle(up, yawFor(axis, side) + Math.PI / 2), one));
              addSolid(p, 1.2);
            }
          }
          continue;
        }

        // Utility poles and wires through the residential districts.
        const side = axis === 'z' ? -1 : 1;
        const bi = axis === 'z' ? Math.max(0, Math.min(N - 1, k - (side < 0 ? 1 : 0))) : j;
        const bj = axis === 'z' ? j : Math.max(0, Math.min(N - 1, k - (side < 0 ? 1 : 0)));
        if (!RESIDENTIAL.has(districtOf(bi, bj).id)) { lastPole = null; continue; }
        for (const a of [mid - 16, mid + 16]) {
          const p = streetPoint(axis, line, a, side * (STREET_HALF + 1.6));
          if (nearRankOrSign(p)) { lastPole = null; continue; }
          const yaw = axis === 'z' ? 0 : Math.PI / 2;
          const m = new THREE.Matrix4().compose(p, q.setFromAxisAngle(up, yaw), one);
          poles.push({ m, c: addSolid(p, 0.3) });
          const tops = utilWires.map((w) => w.clone().applyMatrix4(m));
          if (lastPole) for (let w = 0; w < Math.min(tops.length, lastPole.length); w++) sag(lastPole[w], tops[w], wires, 0.5, 8);
          lastPole = tops;
        }
      }
    }

  const register = (template: THREE.Object3D | undefined, list: { m: THREE.Matrix4; c: Circle | null }[], kind: TreeRef['kind']) => {
    if (!template || !list.length) return;
    const { group, meshes, locals } = instance(template, list.map((l) => l.m));
    list.forEach((l, i) => { if (l.c) treeRefs.set(l.c, { circle: l.c, base: l.m, meshes, locals, index: i, kind }); });
    scene.add(group);
  };
  register(kit.street_lamp, lamps, 'lamp');
  register(kit.utility_pole, poles, 'pole');
  if (kit.trolley_pole && trolley.length) scene.add(instance(kit.trolley_pole, trolley).group);
  if (kit.muni_shelter && shelters.length) scene.add(instance(kit.muni_shelter, shelters).group);
  if (kit.planter && streetTrees.length) scene.add(instance(kit.planter, streetTrees.map((t) => new THREE.Matrix4().makeTranslation(t.c.x, heightAt(t.c.x, t.c.z), t.c.z))).group);
  if (wires.length) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(wires, 3));
    scene.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: 0x1b1722 })));
  }
}

function blockCenter(bi: number, bj: number) {
  const x = -HALF + bi * CELL + CELL / 2;
  const z = -HALF + bj * CELL + CELL / 2;
  return { x, z, y: heightAt(x, z) };
}

function addLandmarks(scene: THREE.Scene) {
  const lam = (c: number) => toon({ color: c });
  // The modelled landmarks (assets/blender/landmarks.py) sit level at the highest ground
  // under their footprint; their plinths reach down the slope. Without a model, primitives.
  const seat = (x: number, z: number, hx: number, hz: number) => {
    let top = -Infinity;
    for (const u of [-1, 0, 1]) for (const v of [-1, 0, 1]) top = Math.max(top, heightAt(x + u * hx, z + v * hz));
    return top;
  };
  const place = (id: string, x: number, y: number, z: number) => {
    const model = landmarkModels[id];
    if (!model) return false;
    model.position.set(x, y, z);
    scene.add(model);
    return true;
  };

  // Salesfarce Tower: tapered rounded obelisk with a glowing crown (the model's `crown` node).
  {
    const { x, z, y } = blockCenter(8, 2);
    if (!place('salesfarce_tower', x, seat(x, z, 19.5, 19.5), z)) {
      const tower = new THREE.Mesh(new THREE.CylinderGeometry(8, 13, 150, 10), lam(0xc9d2d8));
      tower.position.set(x, y + 75, z);
      const crown = new THREE.Mesh(new THREE.CylinderGeometry(6.5, 8, 14, 10), new THREE.MeshBasicMaterial({ color: 0x9fe6ff }));
      crown.position.set(x, y + 157, z);
      const cap = new THREE.Mesh(new THREE.SphereGeometry(6.5, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), lam(0xc9d2d8));
      cap.position.set(x, y + 164, z);
      const base = new THREE.Mesh(new THREE.BoxGeometry(40, 10, 40), lam(0x8c96a0));
      base.position.set(x, y + 3, z);
      tower.castShadow = base.castShadow = true;
      scene.add(tower, crown, cap, base);
    }
  }
  // The Pyramid.
  {
    const { x, z, y } = blockCenter(7, 1);
    if (!place('pyramid', x, seat(x, z, 19.5, 19.5), z)) {
      const pyr = new THREE.Mesh(new THREE.ConeGeometry(19, 110, 4), lam(0xe6e2d6));
      pyr.rotation.y = Math.PI / 4;
      pyr.position.set(x, y + 53, z);
      const spire = new THREE.Mesh(new THREE.ConeGeometry(1.2, 22, 4), lam(0xe6e2d6));
      spire.position.set(x, y + 118, z);
      const base = new THREE.Mesh(new THREE.BoxGeometry(40, 4, 40), lam(0x9d988c));
      base.position.set(x, y + 1, z);
      pyr.castShadow = true;
      scene.add(pyr, spire, base);
    }
  }
  // Ferry Building with clock tower; the model's tower faces west, its promenade the bay.
  {
    const { x, z, y } = blockCenter(9, 1);
    if (!place('ferry_building', x + 2, seat(x + 2, z, 17.5, 19.5), z)) {
      const hall = new THREE.Mesh(new THREE.BoxGeometry(36, 12, 40), lam(0xd8cdb2));
      hall.position.set(x + 2, y + 5, z);
      const tower = new THREE.Mesh(new THREE.BoxGeometry(7, 44, 7), lam(0xe4dac0));
      tower.position.set(x + 2, y + 22, z);
      const cap = new THREE.Mesh(new THREE.ConeGeometry(5.5, 9, 4), lam(0x8a7a5a));
      cap.rotation.y = Math.PI / 4;
      cap.position.set(x + 2, y + 48.5, z);
      const clock = new THREE.Mesh(new THREE.CircleGeometry(2.4, 16), new THREE.MeshBasicMaterial({ color: 0xfffbe8 }));
      clock.position.set(x + 2, y + 36, z + 3.6);
      hall.castShadow = tower.castShadow = true;
      scene.add(hall, tower, cap, clock);
    }
  }
  // Coit Tower on the Russian Hill park, on a round terrace walled against the slope.
  {
    const { x, z, y } = blockCenter(3, 0);
    let ground = -Infinity;
    for (let k = 0; k < 16; k++) ground = Math.max(ground, heightAt(x + 9.5 * Math.cos(k * Math.PI / 8), z + 9.5 * Math.sin(k * Math.PI / 8)));
    if (place('coit_tower', x, ground + 0.2, z)) {
      blocks[0 * N + 3].circles.push({ x, z, r: 9.6 });
    } else {
      const col = new THREE.Mesh(new THREE.CylinderGeometry(3.4, 3.8, 30, 14), lam(0xece5d3));
      col.position.set(x, y + 15, z);
      const top = new THREE.Mesh(new THREE.CylinderGeometry(4.2, 3.4, 3, 14), lam(0xddd4bf));
      top.position.set(x, y + 31, z);
      col.castShadow = true;
      scene.add(col, top);
      blocks[0 * N + 3].circles.push({ x, z, r: 4.2 });
    }
  }
  // City Hall faces east onto its plaza, gilded dome and all; the block is solid as usual.
  {
    const { x, z } = blockCenter(5, 4);
    place('city_hall', x, seat(x, z, 19.5, 19.5), z);
  }
  // The Dragon Gate stands across Grant Ave (the street at x = 128) at the foot of Chinatown.
  // Cabs drive through it: only the two outer pillars, at the back of the sidewalks, are solid.
  {
    const x = -HALF + 7 * CELL, z = -HALF + 2 * CELL + CELL / 2;
    if (place('dragon_gate', x, heightAt(x, z), z))
      for (const sx of [-1, 1]) blockAt(x + sx * 9.8, z)?.circles.push({ x: x + sx * 9.8, z, r: 0.75 });
  }
  // The Palace of Fine Arts in its park: the rotunda (drive through the arches), the
  // colonnade wings, and the lagoon in front, level with the model's water sheet.
  {
    const { x, z } = PALACE;
    if (place('palace_of_fine_arts', x, LAGOON.level + 0.5, z)) {
      const park = blocks[0 * N + 0];
      // Model space (assets/blender/landmarks.py) is east +x, north +y: game z = z - y.
      const solid = (mx: number, my: number, r: number) => park.circles.push({ x: x + mx, z: z - my, r });
      for (let k = 0; k < 8; k++) {
        const a = (2 * Math.PI * (k + 0.5)) / 8;
        solid(-7 + 8.6 * Math.cos(a), 8.6 * Math.sin(a), 1.4);
      }
      for (const [a0, a1] of [[125, 163], [197, 235]])
        for (let k = 0; k < 6; k++) {
          const a = ((a0 + ((a1 - a0) * k) / 5) * Math.PI) / 180;
          solid(6 + 21 * Math.cos(a), 21 * Math.sin(a), 1.6);
        }
      for (const [mx, my] of [[-18, 15], [-18.5, -14], [-12, 18], [-13, -18]]) solid(mx, my, 0.5);
    }
  }
  // Alcatraz: the cellhouse, its administration wing and yard wall, the lighthouse, the
  // water tower's legs, the warden's house and the guard tower. features.ts makes the ground.
  if (place('alcatraz', ALCATRAZ.x, WATER, ALCATRAZ.z)) {
    const solid = (mx: number, my: number, r: number) => extraCircles.push({ x: ALCATRAZ.x + mx, z: ALCATRAZ.z - my, r });
    for (const my of [-6, -1, 4, 9, 14, 18]) solid(-4, my, 6);
    for (const mx of [-8, -4, 0]) solid(mx, -12.4, 3.3);
    for (let k = 0; k <= 7; k++) { solid(-10 - k / 7, 21 + k, 0.7); solid(2 + k / 7, 21 + k, 0.7); solid(-11 + 2 * k, 28, 0.7); }
    solid(-4, -16.5, 2.2);
    for (const [mx, my] of [[4.7, 22.7], [9.3, 22.7], [4.7, 27.3], [9.3, 27.3]]) solid(mx, my, 0.4);
    solid(-9, -25, 3.8);
    solid(8, -24, 1.8);
    for (const my of [5.8, 10.2]) solid(13, my, 0.3);
  }
}

// Somewhere the seabed should stay clear: Alcatraz, and its causeway.
const nearAlcatraz = (x: number, z: number) =>
  (Math.abs(x - ALCATRAZ.x) < 32 && Math.abs(z - ALCATRAZ.z) < 50) || (x > ALCATRAZ.x && x < ALCATRAZ.x + 100 && Math.abs(z - ALCATRAZ.z) < 9);

function makeSeabed() {
  const g = new THREE.Group();
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000), toon({ color: 0xc9b98f }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = SEA_FLOOR - 0.05;
  floor.receiveShadow = true;
  g.add(floor);
  // Rocks you can hit and kelp you can't, out in the bay.
  const r = rng(404);
  const rockGeo = new THREE.IcosahedronGeometry(1, 0);
  const kelpGeo = new THREE.BoxGeometry(0.4, 1, 0.15).translate(0, 0.5, 0);
  const rocks = new THREE.InstancedMesh(rockGeo, toon({ color: 0x7f7a70 }), 70);
  const kelp = new THREE.InstancedMesh(kelpGeo, toon({ color: 0x3f8a4a }), 160);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
  const spot = () => {
    // Somewhere in the open bay, east or north of the city.
    const east = r() < 0.5;
    const along = -HALF - 160 + r() * (2 * HALF + 160);
    const out = HALF + 36 + r() * 130;
    return east ? [out, Math.min(along, HALF)] : [Math.min(along, HALF + 150), -out];
  };
  for (let k = 0; k < 70; k++) {
    const [x, z] = spot();
    const s = (1.2 + r() * 2.2) * (nearAlcatraz(x, z) ? 0 : 1); // none on the island or its causeway
    rocks.setMatrixAt(k, m.compose(new THREE.Vector3(x, SEA_FLOOR + s * 0.3, z), q.setFromEuler(e.set(r() * 3, r() * 3, r() * 3)), new THREE.Vector3(s, s * 0.7, s)));
    if (s > 0) extraCircles.push({ x, z, r: s * 0.9 });
  }
  for (let k = 0; k < 160; k++) {
    const [x, z] = spot();
    const h = (2 + r() * 6) * (nearAlcatraz(x, z) ? 0 : 1);
    kelp.setMatrixAt(k, m.compose(new THREE.Vector3(x, SEA_FLOOR, z), q.setFromEuler(e.set((r() - 0.5) * 0.3, r() * 3, (r() - 0.5) * 0.3)), new THREE.Vector3(1, h, 1)));
  }
  rocks.castShadow = true;
  g.add(rocks, kelp);
  return g;
}

function addGoldenGate(scene: THREE.Scene) {
  const red = toon({ color: 0xc0392b });
  const zc = -HALF - 110;
  const towers = [-340, -150];
  // The model (assets/blender/landmarks.py): origin at the water line midway between the
  // towers, deck and cables included. Each tower stands on a 10 x 18 m pier.
  const model = landmarkModels.golden_gate;
  if (model) {
    model.position.set((towers[0] + towers[1]) / 2, 0, zc);
    scene.add(model);
    for (const tx of towers) for (const off of [-4.5, 0, 4.5]) extraCircles.push({ x: tx, z: zc + off, r: 5 });
    return;
  }
  for (const tx of towers) {
    for (const off of [-5, 5]) {
      extraCircles.push({ x: tx, z: zc + off, r: 2.2 });
      const leg = new THREE.Mesh(new THREE.BoxGeometry(3, 110, 3), red);
      leg.position.set(tx, 33, zc + off);
      scene.add(leg);
    }
    for (const yy of [30, 60, 86]) {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(3, 3, 12), red);
      bar.position.set(tx, yy, zc);
      scene.add(bar);
    }
  }
  const deck = new THREE.Mesh(new THREE.BoxGeometry(520, 2.5, 12), red);
  deck.position.set(-245, 22, zc);
  scene.add(deck);
  for (const off of [-5, 5]) {
    const pts: THREE.Vector3[] = [];
    for (let k = 0; k <= 40; k++) {
      const x = -505 + (k / 40) * 520;
      let y: number;
      if (x < towers[0]) y = 24 + (86 - 24) * ((x + 505) / (towers[0] + 505)) ** 2;
      else if (x > towers[1]) y = 86 - (86 - 24) * ((x - towers[1]) / (15 - towers[1])) ** 0.5;
      else { const t = (x - towers[0]) / (towers[1] - towers[0]); y = 86 - 58 * 4 * t * (1 - t); }
      pts.push(new THREE.Vector3(x, y, zc + off));
    }
    const cable = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 80, 0.6, 5), red);
    scene.add(cable);
  }
}

export const BLOCKS_SIDES: Side[] = ['N', 'S', 'E', 'W'];
