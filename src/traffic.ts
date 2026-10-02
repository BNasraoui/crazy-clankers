import * as THREE from 'three';
import { Car } from './car';
import { CELL, HALF, N, rng } from './world';
import { groundAt, movingRamps, rampGeometry, type Ramp } from './features';
import { toon } from './look';
import { makeCar, makeSedan, makeToaster, makeWedge, type CarModel } from './models';

// Car carriers: the ramp starts at the back and rises over the flatbed.
const CARRIER_RAMP = { back: 4.6, length: 6.2, width: 2.6, lift: 2.3 };

function makeCarrier(): CarModel {
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  const orange = toon(0xe8862a), dark = toon(0x2a2730);
  const box = (w: number, h: number, d: number, m: THREE.Material, x: number, y: number, z: number) => {
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    b.position.set(x, y, z);
    b.castShadow = true;
    body.add(b);
  };
  box(2.3, 2.0, 2.3, orange, 0, 1.55, 3.4); // top at 2.55 m, below the ramp lip (2.65 m)
  box(2.32, 0.6, 1.6, dark, 0, 2.0, 4.0);
  box(2.3, 0.5, 9.4, dark, 0, 0.7, -0.3);
  const ramp = new THREE.Mesh(
    rampGeometry({ x: 0, z: 0, yaw: 0, length: CARRIER_RAMP.length, width: CARRIER_RAMP.width, thickness: 0.4, height: (t) => 0.35 + CARRIER_RAMP.lift * t }, 8, false),
    toon({ vertexColors: true, color: 0xb8b4aa }),
  );
  ramp.position.z = -CARRIER_RAMP.back;
  ramp.castShadow = true;
  body.add(ramp);
  const wheels: THREE.Object3D[] = [];
  for (const z of [3.3, -1.5, -3.2]) for (const x of [-1.05, 1.05]) {
    const w = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.4, 10), dark);
    w.rotation.z = Math.PI / 2;
    w.position.set(x, 0.5, z);
    body.add(w);
    wheels.push(w);
  }
  return { root, body, wheels, steer: [] };
}

interface TCar {
  model: CarModel;
  rival: string | null;
  carrier: boolean;
  ramp?: Ramp;
  axis: 'x' | 'z';
  line: number; // street centreline
  dir: 1 | -1;
  s: number; // position along the street
  speed: number;
  cruise: number;
  stopped: number; // seconds left sitting still after being hit
  blockedFor: number;
  near: boolean;
  hitAt: number;
  honkAt: number;
  x: number;
  z: number;
  // Rammed by the Artemis: off its street, flying and tumbling until it respawns.
  fly: { vx: number; vy: number; vz: number; y: number; rx: number; ry: number; rz: number; sx: number; sy: number; sz: number; t: number } | null;
}

export interface TrafficEvents { impact: number; nearMisses: number; honk: boolean; rams: THREE.Vector3[] }

const COLORS = [0x2d4a7a, 0x8a2b2b, 0x1f1f22, 0xd8d8d8, 0x4a6a3a, 0xc9a227, 0x6a6f78, 0x7a3f8a];
const LANE = 3;
// Each car is three circles along its length.
const PARTS = [-1.4, 0, 1.4];
const CARRIER_PARTS = [2.4, 3.6]; // only the cab is solid; the ramp is for driving on
const PART_R = 1.1;
const MID = 0.85; // half a car's height: a rammed car tumbles about this point

export class Traffic {
  cars: TCar[] = [];
  private clock = 0;
  rammer = false; // the Artemis Go: traffic flies off it instead of stopping it

  // rivals: ids of the robotaxis you aren't driving; some traffic is drawn as them.
  constructor(scene: THREE.Scene, count: number, private rivals: string[] = []) {
    const r = rng(5);
    for (let k = 0; k < count; k++) {
      const pick = r();
      const carrier = k < 6;
      const rival = !carrier && this.rivals.length > 0 && pick > 0.82 ? this.rivals[k % this.rivals.length] : null;
      const model = carrier ? makeCarrier() : rival ? makeCar(rival) : pick < 0.12 ? makeWedge() : pick < 0.27 ? makeToaster() : makeSedan(COLORS[Math.floor(r() * COLORS.length)]);
      scene.add(model.root);
      const cruise = carrier ? 8 : 9 + r() * 4;
      let ramp: Ramp | undefined;
      if (carrier) {
        ramp = { x: 0, z: 0, yaw: 0, length: CARRIER_RAMP.length, width: CARRIER_RAMP.width, height: (t) => 0.35 + CARRIER_RAMP.lift * t };
        movingRamps.push(ramp);
      }
      this.cars.push({
        model, carrier, ramp, rival, axis: r() < 0.5 ? 'x' : 'z', line: -HALF + Math.floor(r() * (N + 1)) * CELL,
        dir: r() < 0.5 ? 1 : -1, s: 0, speed: cruise, cruise, stopped: 0, blockedFor: 0,
        near: false, hitAt: -99, honkAt: -99, x: 0, z: 0, fly: null,
      });
    }
    this.scatter();
  }

  // Re-skin rival robotaxis so none of them matches the cab you chose.
  setRivals(scene: THREE.Scene, rivals: string[]) {
    let k = 0;
    for (const c of this.cars) {
      if (!c.rival) continue;
      const id = rivals[k++ % rivals.length];
      if (id === c.rival) continue;
      scene.remove(c.model.root);
      c.model = makeCar(id);
      c.rival = id;
      scene.add(c.model.root);
    }
  }

  scatter() {
    const r = rng(77);
    for (const c of this.cars) {
      for (let tries = 0; tries < 20; tries++) {
        c.s = -HALF + r() * 2 * HALF;
        this.place(c);
        if (Math.hypot(c.x, c.z + 30) > 40 && !this.cars.some((o) => o !== c && Math.hypot(o.x - c.x, o.z - c.z) < 10)) break;
      }
      c.speed = c.cruise;
      c.stopped = 0;
    }
  }

  private place(c: TCar) {
    // Drive on the right.
    if (c.axis === 'z') { c.x = c.line - LANE * c.dir; c.z = c.s; }
    else { c.x = c.s; c.z = c.line + LANE * c.dir; }
  }

  private heading(c: TCar): [number, number] {
    return c.axis === 'z' ? [0, c.dir] : [c.dir, 0];
  }

  update(dt: number, player: Car, walkers: { x: number; z: number }[] = []): TrafficEvents {
    this.clock += dt;
    const ev: TrafficEvents = { impact: 0, nearMisses: 0, honk: false, rams: [] };
    const pf = player.fwd;
    const playerParts = PARTS.map((o) => [player.pos.x + pf.x * o, player.pos.z + pf.y * o]);

    for (const c of this.cars) {
      if (c.fly) { this.tumble(c, dt, player); continue; }
      const [fx, fz] = this.heading(c);
      let blocked = false;
      let byPlayer = false;
      const check = (ox: number, oz: number) => {
        const dx = ox - c.x, dz = oz - c.z;
        const along = dx * fx + dz * fz;
        const lat = Math.abs(dx * fz - dz * fx);
        return along > 0 && along < 8 && lat < 2.6;
      };
      if (check(player.pos.x, player.pos.z)) { blocked = true; byPlayer = true; }
      if (!blocked && c.blockedFor < 3)
        for (const o of this.cars) if (o !== c && !o.fly && check(o.x, o.z)) { blocked = true; break; }
      if (!blocked) for (const w of walkers) if (check(w.x, w.z)) { blocked = true; break; }

      if (c.stopped > 0) { c.stopped -= dt; c.speed = 0; }
      else if (blocked) { c.blockedFor += dt; c.speed = Math.max(0, c.speed - 25 * dt); }
      else { c.blockedFor = 0; c.speed = Math.min(c.cruise, c.speed + 6 * dt); }
      if (byPlayer && c.blockedFor > 0.8 && this.clock - c.honkAt > 3) {
        c.honkAt = this.clock;
        if (Math.hypot(player.pos.x - c.x, player.pos.z - c.z) < 25) ev.honk = true;
      }

      c.s += c.dir * c.speed * dt;
      if (c.s > HALF + 6) c.s = -HALF - 6;
      if (c.s < -HALF - 6) c.s = HALF + 6;
      this.place(c);
      if (c.ramp) {
        c.ramp.x = c.x - fx * CARRIER_RAMP.back;
        c.ramp.z = c.z - fz * CARRIER_RAMP.back;
        c.ramp.yaw = Math.atan2(fx, fz);
      }

      // Player contact.
      const dxp = player.pos.x - c.x, dzp = player.pos.z - c.z;
      if (Math.abs(dxp) > 12 || Math.abs(dzp) > 12) { c.near = false; continue; }
      const overTop = player.pos.y > groundAt(c.x, c.z, false) + (c.carrier ? 2.4 : 1.7);
      let minD = Infinity;
      for (const o of c.carrier ? CARRIER_PARTS : PARTS) {
        const cx = c.x + fx * o, cz = c.z + fz * o;
        for (const [px, pz] of playerParts) minD = Math.min(minD, Math.hypot(px - cx, pz - cz));
      }
      if (!overTop && minD < PART_R * 2) {
        const d = Math.hypot(dxp, dzp) || 1;
        const nx = dxp / d, nz = dzp / d;
        const push = PART_R * 2 - minD;
        player.pos.x += nx * push;
        player.pos.z += nz * push;
        const rvx = player.vel.x - fx * c.speed, rvz = player.vel.y - fz * c.speed;
        const vn = rvx * nx + rvz * nz;
        if (this.rammer && !c.carrier && -vn > 4) {
          // The Artemis doesn't bounce: the other car does, right off the road.
          const kick = player.speed * 0.9 + 6;
          const r = () => (Math.random() - 0.5) * 2;
          c.fly = { vx: -nx * kick + player.vel.x * 0.3, vy: 6 + player.speed * 0.2, vz: -nz * kick + player.vel.y * 0.3,
            y: groundAt(c.x, c.z, false) + MID, rx: 0, ry: Math.atan2(fx, fz), rz: 0, sx: r() * 6, sy: r() * 5, sz: r() * 6, t: 3.5 };
          c.speed = 0;
          player.vel.multiplyScalar(0.92);
          ev.rams.push(new THREE.Vector3(c.x, c.fly.y + 1, c.z));
          c.near = false;
          continue;
        }
        if (vn < 0) {
          player.vel.x -= nx * vn * 1.4;
          player.vel.y -= nz * vn * 1.4;
          if (-vn > 3) {
            ev.impact = Math.max(ev.impact, -vn);
            c.stopped = 2;
            c.hitAt = this.clock;
          }
        }
        c.near = false;
      } else if (player.speed > 16 && minD < 3.4) {
        c.near = true;
      } else if (c.near && minD > 6) {
        c.near = false;
        if (this.clock - c.hitAt > 1.5) ev.nearMisses++;
      }
    }
    return ev;
  }

  // A rammed car flies, bounces and tumbles, then quietly rejoins traffic somewhere out of sight.
  private tumble(c: TCar, dt: number, player: Car) {
    const f = c.fly!;
    f.vy -= 30 * dt;
    c.x += f.vx * dt; c.z += f.vz * dt; f.y += f.vy * dt;
    f.rx += f.sx * dt; f.ry += f.sy * dt; f.rz += f.sz * dt;
    // f.y is the car's middle (it spins about that), so it never dips into the road.
    const ground = groundAt(c.x, c.z, false) + MID;
    if (f.y < ground) {
      f.y = ground;
      f.vy = Math.abs(f.vy) * 0.35;
      f.vx *= 0.6; f.vz *= 0.6;
      f.sx *= 0.6; f.sy *= 0.6; f.sz *= 0.6;
    }
    f.t -= dt;
    if (f.t > 0) return;
    c.fly = null;
    c.model.body.position.y = 0;
    const along = c.axis === 'z' ? player.pos.z : player.pos.x;
    c.s = along + (along > 0 ? -1 : 1) * (HALF * 0.8); // well away from the cab
    c.speed = c.cruise;
    c.stopped = 0;
    this.place(c);
  }

  sync(dt: number) {
    for (const c of this.cars) {
      if (c.fly) {
        // Spin about the car's middle: the root sits there, the body hangs half a car below it.
        c.model.root.position.set(c.x, c.fly.y, c.z);
        c.model.root.rotation.set(c.fly.rx, c.fly.ry, c.fly.rz, 'YXZ');
        c.model.body.rotation.x = 0;
        c.model.body.position.y = -MID;
        continue;
      }
      const [fx, fz] = this.heading(c);
      const y = groundAt(c.x, c.z, false);
      const slope = (groundAt(c.x + fx * 1.5, c.z + fz * 1.5, false) - groundAt(c.x - fx * 1.5, c.z - fz * 1.5, false)) / 3;
      const { root, body, wheels } = c.model;
      root.position.set(c.x, y, c.z);
      root.rotation.set(0, Math.atan2(fx, fz), 0); // full reset, after any tumble
      body.rotation.x = -Math.atan(slope);
      for (const w of wheels) w.rotation.x += (c.speed * dt) / 0.42;
      if (c.model.spinner) c.model.spinner.rotation.y += dt * 10;
    }
  }
}
