import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { toon } from './look';
import { groundAt } from './features';
import { BLOCKS_SIDES, CELL, CURB_ROAD, CURB_WALK, HALF, N, STREET_HALF, blocks, curb, landmarks, rng, type Side } from './world';
import type { Car } from './car';

// Street junk that goes flying when you hit it. Blockout shapes, merged per kind
// into one instanced mesh each, so 300-odd props cost a handful of draw calls.

export type PropKind = 'hydrant' | 'cone' | 'newsbox' | 'trash' | 'table' | 'fruit' | 'sawhorse' | 'placard';

interface Spec { geo: THREE.BufferGeometry; material: THREE.Material; r: number; h: number; drag: number }

function part(geo: THREE.BufferGeometry, color: number, x = 0, y = 0, z = 0) {
  const g = (geo.index ? geo.toNonIndexed() : geo).translate(x, y, z);
  const c = new THREE.Color(color);
  const n = g.getAttribute('position').count;
  g.setAttribute('color', new THREE.Float32BufferAttribute(new Array(n).fill(0).flatMap(() => [c.r, c.g, c.b]), 3));
  return g;
}

function placardTexture() {
  const c = document.createElement('canvas');
  c.width = 256;
  c.height = 128;
  const g = c.getContext('2d')!;
  g.fillStyle = '#f4f1e8';
  g.fillRect(0, 0, 256, 128);
  g.fillStyle = '#d23b2e';
  g.font = '900 44px Impact, "Arial Black", sans-serif';
  g.textAlign = 'center';
  g.fillText('NO', 128, 52);
  g.fillText('ROBOTAXIS', 128, 104);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function specs(): Record<PropKind, Spec> {
  const vc = toon({ vertexColors: true });
  const merge = (...parts: THREE.BufferGeometry[]) => mergeGeometries(parts)!;
  return {
    hydrant: { r: 0.35, h: 0.9, drag: 0.94, material: vc, geo: merge(
      part(new THREE.CylinderGeometry(0.2, 0.24, 0.7, 10), 0xd23b2e, 0, 0.35, 0),
      part(new THREE.CylinderGeometry(0.15, 0.26, 0.16, 10), 0xd23b2e, 0, 0.78, 0),
      part(new THREE.BoxGeometry(0.62, 0.12, 0.12), 0xb8b2a4, 0, 0.5, 0)) },
    cone: { r: 0.3, h: 0.75, drag: 0.995, material: vc, geo: merge(
      part(new THREE.ConeGeometry(0.24, 0.72, 10), 0xf26a1b, 0, 0.42, 0),
      part(new THREE.CylinderGeometry(0.17, 0.19, 0.1, 10), 0xf4f1e8, 0, 0.4, 0),
      part(new THREE.BoxGeometry(0.5, 0.06, 0.5), 0x26232b, 0, 0.03, 0)) },
    newsbox: { r: 0.4, h: 1.05, drag: 0.97, material: vc, geo: merge(
      part(new THREE.BoxGeometry(0.5, 1, 0.45), 0x2d6fd2, 0, 0.5, 0),
      part(new THREE.BoxGeometry(0.4, 0.25, 0.47), 0xe8eef2, 0, 0.75, 0)) },
    trash: { r: 0.35, h: 1, drag: 0.97, material: vc, geo: merge(
      part(new THREE.CylinderGeometry(0.3, 0.27, 0.9, 10), 0x3b7d4a, 0, 0.45, 0),
      part(new THREE.CylinderGeometry(0.33, 0.33, 0.08, 10), 0x2c5e38, 0, 0.93, 0)) },
    table: { r: 0.6, h: 0.8, drag: 0.98, material: vc, geo: merge(
      part(new THREE.CylinderGeometry(0.55, 0.55, 0.06, 12), 0xf4f1e8, 0, 0.76, 0),
      part(new THREE.CylinderGeometry(0.05, 0.05, 0.74, 6), 0x26232b, 0, 0.37, 0),
      part(new THREE.CylinderGeometry(0.25, 0.25, 0.04, 10), 0x26232b, 0, 0.02, 0),
      part(new THREE.CylinderGeometry(0.04, 0.04, 2.2, 6), 0xe8e2d4, 0, 1.6, 0),
      part(new THREE.ConeGeometry(1.2, 0.5, 8), 0xe2483b, 0, 2.6, 0)) },
    fruit: { r: 0.85, h: 1, drag: 0.93, material: vc, geo: merge(
      part(new THREE.BoxGeometry(1.5, 0.8, 0.8), 0x9a7650, 0, 0.4, 0),
      ...[0xe2483b, 0xf39c2b, 0xf3c530, 0x7cbf4a, 0xe2483b, 0xf39c2b, 0x7cbf4a, 0xf3c530].map((c, i) =>
        part(new THREE.BoxGeometry(0.3, 0.3, 0.3), c, -0.55 + (i % 4) * 0.36, 0.95, i < 4 ? -0.18 : 0.18))) },
    sawhorse: { r: 1.1, h: 1, drag: 0.98, material: vc, geo: merge(
      part(new THREE.BoxGeometry(2.4, 0.3, 0.08), 0xf4f1e8, 0, 0.85, 0),
      part(new THREE.BoxGeometry(0.5, 0.31, 0.09), 0xd23b2e, -0.7, 0.85, 0),
      part(new THREE.BoxGeometry(0.5, 0.31, 0.09), 0xd23b2e, 0.7, 0.85, 0),
      part(new THREE.BoxGeometry(0.08, 0.85, 0.5), 0x9a7650, -1, 0.42, 0),
      part(new THREE.BoxGeometry(0.08, 0.85, 0.5), 0x9a7650, 1, 0.42, 0)) },
    placard: { r: 0.5, h: 2.4, drag: 0.99, material: toon({ map: placardTexture() }), geo: merge(
      new THREE.BoxGeometry(1.1, 0.6, 0.05).translate(0, 2.1, 0).toNonIndexed(),
      new THREE.BoxGeometry(0.06, 1.9, 0.06).translate(0, 0.95, 0).toNonIndexed()) },
  };
}

interface Prop {
  kind: PropKind;
  index: number;
  home: THREE.Vector3;
  yaw: number;
  pos: THREE.Vector3;
  vel: THREE.Vector3;
  quat: THREE.Quaternion;
  spin: THREE.Vector3;
  state: 'idle' | 'flying' | 'resting';
  t: number;
}

export interface PropHit { kind: PropKind; pos: THREE.Vector3 }

const ONE = new THREE.Vector3(1, 1, 1);
const cellKey = (x: number, z: number) => `${Math.floor((x + HALF) / CELL)},${Math.floor((z + HALF) / CELL)}`;

export class Props {
  private spec = specs();
  private props: Prop[] = [];
  private meshes = new Map<PropKind, THREE.InstancedMesh>();
  private cells = new Map<string, Prop[]>();
  private dirty = new Set<PropKind>();
  private m = new THREE.Matrix4();

  constructor(scene: THREE.Scene) {
    const places: { kind: PropKind; x: number; z: number; yaw: number }[] = [];
    const r = rng(77);
    const pick = <T,>(a: T[]) => a[Math.floor(r() * a.length)];
    const sidewalk = (bi: number, bj: number, side: Side, t: number, fromCurb: number) => {
      const c = curb(bi, bj, side, t);
      // fromCurb is measured from the curb edge; walk and road are known distances from the centreline.
      const k = (STREET_HALF + fromCurb - CURB_ROAD) / (CURB_WALK - CURB_ROAD);
      return { x: c.road.x + (c.walk.x - c.road.x) * k, z: c.road.z + (c.walk.z - c.road.z) * k, yaw: c.facing };
    };
    const farFromLandmarks = (x: number, z: number) => landmarks.every((l) => Math.hypot(l.curb.walk.x - x, l.curb.walk.z - z) > 6);

    for (const b of blocks) {
      if (b.kind === 'park') continue;
      const p = sidewalk(b.bi, b.bj, pick(BLOCKS_SIDES), r() < 0.5 ? 0.02 : 0.98, 1);
      places.push({ kind: 'hydrant', ...p });
      if (b.kind === 'downtown' || b.kind === 'landmark')
        for (let k = 0; k < 3; k++) places.push({ kind: 'table', ...sidewalk(b.bi, b.bj, pick(['N', 'S'] as Side[]), r(), 2.6) });
    }
    const scatter = (kind: PropKind, count: number, fromCurb: number) => {
      for (let k = 0; k < count; k++) {
        const p = sidewalk(Math.floor(r() * N), Math.floor(r() * N), pick(BLOCKS_SIDES), r(), fromCurb);
        if (farFromLandmarks(p.x, p.z)) places.push({ kind, ...p });
      }
    };
    scatter('newsbox', 40, 2.8);
    scatter('trash', 50, 1.2);
    scatter('fruit', 8, 2.4);
    scatter('cone', 25, -0.8);

    // Cone protests: a line of cones across a street, a sawhorse and two placards.
    const avoid = [[0, -30], [-192, 192], [-128, -256]];
    let sites = 0;
    for (let tries = 0; sites < 6 && tries < 60; tries++) {
      const alongZ = r() < 0.5;
      const line = -HALF + (1 + Math.floor(r() * (N - 1))) * CELL;
      const mid = -HALF + Math.floor(r() * N) * CELL + CELL / 2;
      const [cx, cz] = alongZ ? [line, mid] : [mid, line];
      if (avoid.some(([ax, az]) => Math.hypot(ax - cx, az - cz) < 70)) continue;
      sites++;
      for (let k = -4; k <= 4; k++) {
        if (k === 0) continue;
        const o = k * 1.35;
        places.push({ kind: 'cone', x: alongZ ? cx + o : cx, z: alongZ ? cz : cz + o, yaw: r() * 6 });
      }
      places.push({ kind: 'sawhorse', x: cx, z: cz, yaw: alongZ ? 0 : Math.PI / 2 });
      for (const s of [-1, 1]) {
        const o = s * 7.2;
        places.push({ kind: 'placard', x: alongZ ? cx + o : cx, z: alongZ ? cz : cz + o, yaw: alongZ ? (s < 0 ? Math.PI / 2 : -Math.PI / 2) : (s < 0 ? 0 : Math.PI) });
      }
    }

    const counts = new Map<PropKind, number>();
    for (const p of places) counts.set(p.kind, (counts.get(p.kind) ?? 0) + 1);
    for (const [kind, n] of counts) {
      const sp = this.spec[kind];
      const mesh = new THREE.InstancedMesh(sp.geo, sp.material, n);
      mesh.castShadow = true;
      mesh.frustumCulled = false;
      this.meshes.set(kind, mesh);
      scene.add(mesh);
    }
    const used = new Map<PropKind, number>();
    for (const p of places) {
      const index = used.get(p.kind) ?? 0;
      used.set(p.kind, index + 1);
      const home = new THREE.Vector3(p.x, groundAt(p.x, p.z, false), p.z);
      const prop: Prop = {
        kind: p.kind, index, home, yaw: p.yaw, pos: home.clone(), vel: new THREE.Vector3(),
        quat: new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), p.yaw), spin: new THREE.Vector3(),
        state: 'idle', t: 0,
      };
      this.props.push(prop);
      this.place(prop);
      this.index(prop);
    }
    for (const mesh of this.meshes.values()) mesh.instanceMatrix.needsUpdate = true;
  }

  private place(p: Prop) {
    this.meshes.get(p.kind)!.setMatrixAt(p.index, this.m.compose(p.pos, p.quat, ONE));
    this.dirty.add(p.kind);
  }

  private index(p: Prop) {
    const key = cellKey(p.home.x, p.home.z);
    const list = this.cells.get(key) ?? [];
    list.push(p);
    this.cells.set(key, list);
  }

  reset() {
    for (const p of this.props) this.goHome(p);
  }

  private goHome(p: Prop) {
    p.state = 'idle';
    p.pos.copy(p.home);
    p.vel.set(0, 0, 0);
    p.quat.setFromAxisAngle(new THREE.Vector3(0, 1, 0), p.yaw);
    this.place(p);
  }

  update(dt: number, car: Car): PropHit[] {
    const hits: PropHit[] = [];
    const speed = car.speed;
    if (speed > 2) {
      const ci = Math.floor((car.pos.x + HALF) / CELL), cj = Math.floor((car.pos.z + HALF) / CELL);
      for (let di = -1; di <= 1; di++)
        for (let dj = -1; dj <= 1; dj++)
          for (const p of this.cells.get(`${ci + di},${cj + dj}`) ?? []) {
            if (p.state !== 'idle') continue;
            const sp = this.spec[p.kind];
            if (Math.hypot(p.pos.x - car.pos.x, p.pos.z - car.pos.z) > 1.7 + sp.r) continue;
            if (car.pos.y > p.pos.y + sp.h) continue; // flew over it
            p.state = 'flying';
            p.t = 0;
            const k = 1 + Math.random() * 0.5;
            p.vel.set(car.vel.x * k + (Math.random() - 0.5) * 4, 5 + Math.random() * 6 + speed * 0.12, car.vel.y * k + (Math.random() - 0.5) * 4);
            p.spin.set((Math.random() - 0.5) * 16, (Math.random() - 0.5) * 10, (Math.random() - 0.5) * 16);
            car.vel.multiplyScalar(sp.drag);
            hits.push({ kind: p.kind, pos: p.pos.clone() });
          }
    }

    const q = new THREE.Quaternion(), e = new THREE.Euler();
    for (const p of this.props) {
      if (p.state === 'idle') continue;
      p.t += dt;
      if (p.state === 'resting') {
        // Tidy up once you're well away.
        if (p.t > 20 && Math.hypot(p.home.x - car.pos.x, p.home.z - car.pos.z) > 60) this.goHome(p);
        continue;
      }
      p.vel.y -= 30 * dt;
      p.pos.addScaledVector(p.vel, dt);
      p.quat.multiply(q.setFromEuler(e.set(p.spin.x * dt, p.spin.y * dt, p.spin.z * dt)));
      const g = groundAt(p.pos.x, p.pos.z);
      if (p.pos.y < g) {
        p.pos.y = g;
        p.vel.y = -p.vel.y * 0.35;
        p.vel.x *= 0.6;
        p.vel.z *= 0.6;
        p.spin.multiplyScalar(0.6);
        if (p.vel.lengthSq() < 2) { p.state = 'resting'; p.t = 0; }
      }
      this.place(p);
    }
    for (const kind of this.dirty) this.meshes.get(kind)!.instanceMatrix.needsUpdate = true;
    this.dirty.clear();
    return hits;
  }
}

// ---------- effects ----------

interface Particle { pos: THREE.Vector3; vel: THREE.Vector3; life: number; size: number }

// Splashes, debris and spray: small cubes on simple ballistic paths.
export class Particles {
  private mesh: THREE.InstancedMesh;
  private items: Particle[] = [];
  private next = 0;
  private m = new THREE.Matrix4();

  constructor(scene: THREE.Scene, private max = 400) {
    this.mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), toon(), max);
    this.mesh.frustumCulled = false;
    for (let i = 0; i < max; i++) {
      this.items.push({ pos: new THREE.Vector3(), vel: new THREE.Vector3(), life: 0, size: 0 });
      this.mesh.setMatrixAt(i, this.m.makeScale(0, 0, 0));
      this.mesh.setColorAt(i, new THREE.Color(0xffffff));
    }
    scene.add(this.mesh);
  }

  emit(at: THREE.Vector3, count: number, color: number, speed: number, up: number, size = 0.35) {
    const c = new THREE.Color(color);
    for (let k = 0; k < count; k++) {
      const i = this.next;
      this.next = (this.next + 1) % this.max;
      const p = this.items[i];
      const a = Math.random() * Math.PI * 2, s = speed * (0.4 + Math.random() * 0.6);
      p.pos.copy(at);
      p.vel.set(Math.cos(a) * s, up * (0.5 + Math.random() * 0.8), Math.sin(a) * s);
      p.life = 0.8 + Math.random() * 0.8;
      p.size = size * (0.6 + Math.random() * 0.8);
      this.mesh.setColorAt(i, c);
    }
    this.mesh.instanceColor!.needsUpdate = true;
  }

  update(dt: number) {
    let any = false;
    this.items.forEach((p, i) => {
      if (p.life <= 0) return;
      any = true;
      p.life -= dt;
      p.vel.y -= 25 * dt;
      p.pos.addScaledVector(p.vel, dt);
      const s = p.life > 0 ? p.size * Math.min(1, p.life * 2) : 0;
      this.mesh.setMatrixAt(i, this.m.makeScale(s, s, s).setPosition(p.pos));
    });
    if (any) this.mesh.instanceMatrix.needsUpdate = true;
  }
}

interface Geyser { at: THREE.Vector3; t: number; group: THREE.Group; column: THREE.Mesh; lastLaunch: number }

// A broken hydrant: a water column that will happily launch a taxi.
export class Geysers {
  private list: Geyser[] = [];
  private colGeo = new THREE.CylinderGeometry(0.45, 0.9, 1, 10, 1, true).translate(0, 0.5, 0);
  private colMat = toon({ color: 0xcfeaf7, side: THREE.DoubleSide });
  static LIFE = 10;
  static HEIGHT = 9;

  constructor(private scene: THREE.Scene, private particles: Particles) {}

  spawn(at: THREE.Vector3) {
    const group = new THREE.Group();
    const column = new THREE.Mesh(this.colGeo, this.colMat);
    group.add(column);
    group.position.copy(at);
    this.scene.add(group);
    this.list.push({ at: at.clone(), t: 0, group, column, lastLaunch: -9 });
  }

  // Returns true when the cab is inside a geyser that should launch it.
  update(dt: number, car: Car): boolean {
    let launch = false;
    for (const g of this.list) {
      g.t += dt;
      const grow = Math.min(1, g.t * 3) * Math.min(1, (Geysers.LIFE - g.t) * 1.5);
      const h = Geysers.HEIGHT * grow * (1 + Math.sin(g.t * 20) * 0.05);
      g.column.scale.set(1 + Math.sin(g.t * 13) * 0.08, Math.max(0.01, h), 1 + Math.cos(g.t * 11) * 0.08);
      if (Math.random() < dt * 30) this.particles.emit(g.at.clone().setY(g.at.y + h), 3, 0xe6f6ff, 4, 4, 0.3);
      const near = Math.hypot(car.pos.x - g.at.x, car.pos.z - g.at.z) < 2.6 && car.pos.y < g.at.y + h;
      if (near && h > 3 && g.t - g.lastLaunch > 1.2) { g.lastLaunch = g.t; launch = true; }
    }
    for (const g of this.list.filter((g) => g.t > Geysers.LIFE)) this.scene.remove(g.group);
    this.list = this.list.filter((g) => g.t <= Geysers.LIFE);
    return launch;
  }

  reset() {
    for (const g of this.list) this.scene.remove(g.group);
    this.list = [];
  }
}
