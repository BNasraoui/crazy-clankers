import * as THREE from 'three';
import { ALCATRAZ, CELL, HALF, N, SEA_FLOOR, WATER, blocks, heightAt, terrainAt } from './world';
import { toon } from './look';

// Set pieces: drivable ramps layered on top of the terrain. The car, traffic
// and props all ask groundAt(), so anything registered here just works.
// These are blockouts: the numbers are the tuned gameplay, and an art pass
// must keep them (see docs/art/ASSETS.md).

export interface Ramp {
  x: number; // start of the ramp (t = 0)
  z: number;
  yaw: number; // direction of travel up the ramp, 0 = +Z
  length: number;
  width: number;
  height: (t: number) => number; // height at t in 0..1, above the terrain or above `abs`
  abs?: number; // absolute base height (piers, boat ramps); otherwise follows the terrain
  thickness?: number; // for decks over water: how deep the visible slab is
}

export const ramps: Ramp[] = [];
// Ramps that move (car-carrier trucks). Traffic ignores these for its own height.
export const movingRamps: Ramp[] = [];

function rampAt(r: Ramp, x: number, z: number): number | null {
  const dx = x - r.x, dz = z - r.z;
  if (dx * dx + dz * dz > (r.length + r.width) ** 2) return null;
  const s = Math.sin(r.yaw), c = Math.cos(r.yaw);
  const a = dx * s + dz * c;
  const l = dx * c - dz * s;
  if (a < 0 || a > r.length || Math.abs(l) > r.width / 2) return null;
  return (r.abs ?? terrainAt(x, z)) + r.height(a / r.length);
}

// Alcatraz (assets/blender/landmarks.py AZ_*): a flat top, an ellipse 34 x 72 m, and cliffs
// that are offset ellipses down to the sea floor: [offset from the top's edge, height above
// the water]. The model is built from the same numbers.
const AZ_RX = 17, AZ_RZ = 36;
const AZ_CLIFF = [[0, 7], [0.6, 4.6], [1.7, 1.6], [3.2, -2.4], [4.7, -6.8], [5.8, -10.4], [6.4, -12.5]];

function islandAt(x: number, z: number): number | null {
  const lx = x - ALCATRAZ.x, lz = z - ALCATRAZ.z;
  const last = AZ_CLIFF[AZ_CLIFF.length - 1][0];
  if (Math.abs(lx) > AZ_RX + last || Math.abs(lz) > AZ_RZ + last) return null;
  const out = (o: number) => (lx / (AZ_RX + o)) ** 2 + (lz / (AZ_RZ + o)) ** 2 - 1;
  if (out(0) <= 0) return ALCATRAZ.top;
  if (out(last) > 0) return null;
  let lo = 0, hi = last; // the offset ellipse through this point
  for (let k = 0; k < 14; k++) {
    const mid = (lo + hi) / 2;
    if (out(mid) > 0) lo = mid; else hi = mid;
  }
  for (let k = 1; k < AZ_CLIFF.length; k++) {
    const [o0, h0] = AZ_CLIFF[k - 1], [o1, h1] = AZ_CLIFF[k];
    if (lo <= o1) return WATER + h0 + ((h1 - h0) * (lo - o0)) / (o1 - o0);
  }
  return null;
}

export function groundAt(x: number, z: number, moving = true): number {
  let h = terrainAt(x, z);
  const island = islandAt(x, z);
  if (island !== null && island > h) h = island;
  for (const r of ramps) {
    const v = rampAt(r, x, z);
    if (v !== null && v > h) h = v;
  }
  if (moving)
    for (const r of movingRamps) {
      const v = rampAt(r, x, z);
      if (v !== null && v > h) h = v;
    }
  return h;
}

// Builds a ramp's visible slab: top surface, side walls and end faces.
export function rampGeometry(r: Ramp, steps = 16, world = true) {
  const pos: number[] = [];
  const col: number[] = [];
  const s = Math.sin(r.yaw), c = Math.cos(r.yaw);
  const pt = (a: number, l: number) => {
    const x = (world ? r.x : 0) + s * a + c * l;
    const z = (world ? r.z : 0) + c * a - s * l;
    const wx = r.x + s * a + c * l, wz = r.z + c * a - s * l;
    const top = (r.abs ?? (world ? terrainAt(wx, wz) : 0)) + r.height(a / r.length);
    const bottom = r.thickness !== undefined ? top - r.thickness : (world ? terrainAt(wx, wz) : 0) - 0.4;
    return { x, z, top, bottom };
  };
  const quad = (p: THREE.Vector3Tuple[], color: THREE.Color) => {
    for (const i of [0, 1, 2, 0, 2, 3]) { pos.push(...p[i]); col.push(color.r, color.g, color.b); }
  };
  const base = new THREE.Color(0xffffff), stripe = new THREE.Color(0xf3c530), dark = new THREE.Color(0x2a2730);
  const w = r.width / 2;
  for (let i = 0; i < steps; i++) {
    const a0 = (i / steps) * r.length, a1 = ((i + 1) / steps) * r.length;
    const L0 = pt(a0, -w), R0 = pt(a0, w), L1 = pt(a1, -w), R1 = pt(a1, w);
    const lip = i >= steps - 2;
    quad([[L0.x, L0.top, L0.z], [L1.x, L1.top, L1.z], [R1.x, R1.top, R1.z], [R0.x, R0.top, R0.z]], lip ? (i % 2 ? stripe : dark) : base);
    quad([[L0.x, L0.bottom, L0.z], [L1.x, L1.bottom, L1.z], [L1.x, L1.top, L1.z], [L0.x, L0.top, L0.z]], base);
    quad([[R0.x, R0.top, R0.z], [R1.x, R1.top, R1.z], [R1.x, R1.bottom, R1.z], [R0.x, R0.bottom, R0.z]], base);
  }
  for (const a of [0, r.length]) {
    const L = pt(a, -w), R = pt(a, w);
    const face: THREE.Vector3Tuple[] = [[L.x, L.bottom, L.z], [L.x, L.top, L.z], [R.x, R.top, R.z], [R.x, R.bottom, R.z]];
    quad(a === 0 ? face : [face[3], face[2], face[1], face[0]], dark);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  geo.computeVertexNormals();
  return geo;
}

function addRamp(scene: THREE.Scene, r: Ramp, color: number) {
  ramps.push(r);
  const mesh = new THREE.Mesh(rampGeometry(r), toon({ color, vertexColors: true, side: THREE.DoubleSide }));
  mesh.castShadow = mesh.receiveShadow = true;
  scene.add(mesh);
  return mesh;
}

const EAST = Math.PI / 2, WEST = -Math.PI / 2, SOUTH = 0;

export function buildFeatures(scene: THREE.Scene) {
  // Twin Peaks: a kicker on the summit that throws you east, over two of the
  // steepest blocks in the city (56.9 m at the top, 11.7 m two blocks down).
  addRamp(scene, { x: -186, z: 192, yaw: EAST, length: 16, width: 10, height: (t) => 10 * t }, 0xd8d2c4);
  addSutroTower(scene);

  // Lombard: the crooked street, which a robotaxi simply flies over. A lip at
  // the top of the steepest block on Russian Hill (37 m down to 15.5 m, heading west).
  addRamp(scene, { x: -130, z: -256, yaw: WEST, length: 7, width: 12, height: (t) => 1.8 * t }, 0xb04a3a);
  addCrookedStreet(scene);

  // Piers along the Embarcadero, either side of the Ferry Building, each with a
  // kicker at the end that launches you into the bay.
  for (const z of [-256, -192, -128]) {
    const deck = heightAt(HALF, z);
    const r: Ramp = {
      x: HALF - 2, z, yaw: EAST, length: 85, width: 12, abs: deck, thickness: 1.2,
      height: (t) => (t < 0.86 ? 0 : ((t - 0.86) / 0.14) * 2.4),
    };
    addRamp(scene, r, 0x9a7650);
    addPilings(scene, r);
  }

  // Alcatraz's causeway: from the sea floor east of the island up to the landing, 76 m at
  // about 14 degrees. The island's model draws it, so it is only registered here.
  ramps.push({
    x: ALCATRAZ.x + 93, z: ALCATRAZ.z, yaw: WEST, length: 76, width: 10, abs: SEA_FLOOR,
    height: (t) => t * (ALCATRAZ.top - SEA_FLOOR),
  });

  // Boat ramps: the only way back out of the bay.
  for (const [x, z, yaw] of [[HALF + 60, -64, WEST], [192, -HALF - 60, SOUTH]] as const) {
    const shore = heightAt(Math.min(x, HALF), Math.max(z, -HALF));
    addRamp(scene, {
      x, z, yaw, length: 54, width: 12, abs: SEA_FLOOR, thickness: 1,
      height: (t) => t * (shore - SEA_FLOOR),
    }, 0xa9a69c);
  }
}

function addPilings(scene: THREE.Scene, r: Ramp) {
  const count = Math.floor(r.length / 10) * 2;
  const geo = new THREE.CylinderGeometry(0.35, 0.35, 1, 6);
  const inst = new THREE.InstancedMesh(geo, toon({ color: 0x5d4632 }), count);
  const m = new THREE.Matrix4();
  let k = 0;
  for (let a = 5; a < r.length && k < count; a += 10)
    for (const l of [-r.width / 2 + 0.6, r.width / 2 - 0.6]) {
      const x = r.x + Math.sin(r.yaw) * a + Math.cos(r.yaw) * l;
      const z = r.z + Math.cos(r.yaw) * a - Math.sin(r.yaw) * l;
      const top = r.abs! - r.thickness!;
      m.makeScale(1, top - SEA_FLOOR, 1).setPosition(x, (top + SEA_FLOOR) / 2, z);
      inst.setMatrixAt(k++, m);
    }
  scene.add(inst);
}

// Brick switchbacks and hedges on the slope below the Lombard lip. Decoration only:
// you're meant to fly over them.
function addCrookedStreet(scene: THREE.Scene) {
  const hedge = new THREE.BoxGeometry(1.2, 0.9, 1);
  const hedges = new THREE.InstancedMesh(hedge, toon({ color: 0x3f8a4a }), 7);
  const flowers = new THREE.InstancedMesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), toon({ color: 0xe86a9a }), 28);
  const m = new THREE.Matrix4();
  for (let k = 0; k < 7; k++) {
    const x = -140 - k * 6.5;
    const left = k % 2 === 0;
    const z = -256 + (left ? -2.5 : 2.5);
    const y = terrainAt(x, z) + 0.3;
    hedges.setMatrixAt(k, m.makeScale(1, 1, 11).setPosition(x, y, z));
    for (let f = 0; f < 4; f++) {
      const fz = z - 4.5 + f * 3;
      flowers.setMatrixAt(k * 4 + f, m.makeScale(1, 1, 1).setPosition(x, terrainAt(x, fz) + 0.95, fz));
    }
  }
  scene.add(hedges, flowers);
}

// Sutro Tower on the Twin Peaks park: three red-and-white legs.
function addSutroTower(scene: THREE.Scene) {
  const bi = 1, bj = 8;
  const cx = -HALF + bi * CELL + CELL / 2, cz = -HALF + bj * CELL + CELL / 2;
  const base = heightAt(cx, cz);
  const red = toon({ color: 0xd2453a }), white = toon({ color: 0xf2efe8 });
  const legs = [0, 2.094, 4.189].map((a) => new THREE.Vector3(Math.cos(a) * 7, 0, Math.sin(a) * 7));
  const H = 75;
  for (const leg of legs) {
    for (let k = 0; k < 6; k++) {
      const t0 = k / 6, t1 = (k + 1) / 6;
      const p0 = leg.clone().multiplyScalar(1 - t0 * 0.85).setY(t0 * H);
      const p1 = leg.clone().multiplyScalar(1 - t1 * 0.85).setY(t1 * H);
      const len = p0.distanceTo(p1);
      const seg = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, len, 6), k % 2 ? white : red);
      seg.position.copy(p0).add(p1).multiplyScalar(0.5).add(new THREE.Vector3(cx, base, cz));
      seg.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), p1.clone().sub(p0).normalize());
      seg.castShadow = true;
      scene.add(seg);
    }
  }
  for (const y of [40, 58, 72]) {
    const arm = new THREE.Mesh(new THREE.BoxGeometry(16 - y * 0.12, 1, 1), y === 72 ? red : white);
    arm.position.set(cx, base + y, cz);
    scene.add(arm);
  }
  blocks[bj * N + bi].circles.push({ x: cx, z: cz, r: 8 });
}
