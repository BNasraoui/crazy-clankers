import * as THREE from 'three';
import { groundAt } from './features';
import { instance, kit } from './scenery';
import type { Car } from './car';

// A Powell-style cable car line: tracks down the middle of the x = 0 street over
// Nob Hill, and two cable cars shuttling up and down it. They're solid; the cab
// can hit them (or jump over them).

const LINE_X = 0;
const Z_START = -300;
const Z_END = 120;
const SPEED = 4.5; // m/s, about 10 mph like the real thing
const WAIT = 5; // seconds at each terminus
const PARTS = [-3.2, -1.6, 0, 1.6, 3.2]; // collision circles along its length
const PART_R = 1.25;

interface Car_ { root: THREE.Object3D; wheels: THREE.Object3D[]; z: number; dir: 1 | -1; wait: number; stopped: number; speed: number }

export class CableCars {
  private cars: Car_[] = [];

  constructor(scene: THREE.Scene) {
    const track = kit.cable_car_track, model = kit.cable_car;
    if (track) {
      const mats: THREE.Matrix4[] = [];
      for (let z = Z_START; z < Z_END; z += 10) {
        const zc = z + 5;
        const slope = (groundAt(LINE_X, zc + 4, false) - groundAt(LINE_X, zc - 4, false)) / 8;
        const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -Math.atan(slope));
        mats.push(new THREE.Matrix4().compose(new THREE.Vector3(LINE_X, groundAt(LINE_X, zc, false) + 0.02, zc), q, new THREE.Vector3(1, 1, 1)));
      }
      const t = instance(track, mats, false);
      scene.add(t.group);
    }
    if (!model) return;
    for (const [z, dir] of [[Z_START + 30, 1], [Z_END - 30, -1]] as const) {
      const root = model.clone(true);
      const wheels: THREE.Object3D[] = [];
      root.traverse((o) => { if (o.name.startsWith('wheel')) wheels.push(o); });
      scene.add(root);
      this.cars.push({ root, wheels, z, dir, wait: 0, stopped: 0, speed: SPEED });
    }
  }

  // Moves the cars and pushes the cab out of them. Returns the impact speed of any hit.
  update(dt: number, player: Car): number {
    let impact = 0;
    for (const c of this.cars) {
      if (c.wait > 0) c.wait -= dt;
      else if (c.stopped > 0) c.stopped -= dt;
      else {
        // Stop for the cab if it's parked on the tracks ahead.
        const ahead = (player.pos.z - c.z) * c.dir;
        const blocked = ahead > 3 && ahead < 10 && Math.abs(player.pos.x - LINE_X) < 2.2;
        c.speed = blocked ? Math.max(0, c.speed - 8 * dt) : Math.min(SPEED, c.speed + 2 * dt);
        c.z += c.dir * c.speed * dt;
        if (c.z > Z_END - 6 || c.z < Z_START + 6) { c.dir = c.dir === 1 ? -1 : 1; c.wait = WAIT; c.z = Math.max(Z_START + 6, Math.min(Z_END - 6, c.z)); }
      }
      const y = groundAt(LINE_X, c.z, false);
      const slope = (groundAt(LINE_X, c.z + 3, false) - groundAt(LINE_X, c.z - 3, false)) / 6;
      c.root.position.set(LINE_X, y, c.z);
      c.root.rotation.set(-Math.atan(slope) * c.dir, c.dir === 1 ? 0 : Math.PI, 0, 'YXZ');
      for (const w of c.wheels) w.rotation.x += (c.speed * dt) / 0.35;

      // Collision with the cab (unless it's flying over).
      if (player.pos.y > y + 3.0 || Math.abs(player.pos.z - c.z) > 8 || Math.abs(player.pos.x - LINE_X) > 4) continue;
      for (const o of PARTS) {
        const dx = player.pos.x - LINE_X, dz = player.pos.z - (c.z + o);
        const d = Math.hypot(dx, dz);
        if (d < PART_R + 1.4 && d > 1e-4) {
          const nx = dx / d, nz = dz / d;
          player.pos.x = LINE_X + nx * (PART_R + 1.4);
          player.pos.z = c.z + o + nz * (PART_R + 1.4);
          const vn = player.vel.x * nx + player.vel.y * nz - c.dir * c.speed * nz;
          if (vn < 0) {
            player.vel.x -= nx * vn * 1.4;
            player.vel.y -= nz * vn * 1.4;
            impact = Math.max(impact, -vn);
            c.stopped = 2;
          }
        }
      }
    }
    return impact;
  }
}
