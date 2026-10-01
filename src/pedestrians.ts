import * as THREE from 'three';
import { CHARACTER_LAYER } from './anime';
import { groundAt } from './features';
import { CELL, HALF, N, rng } from './world';
import type { Car } from './car';

// Pedestrians are 2D sprites standing in the 3D world (like Paper Mario or
// Octopath Traveler). Each one always turns to face the camera and shows the
// drawing that matches the viewing angle: front, back, or a side walk cycle.
// They always dive out of the way; nobody gets run over in Crazy Clankers.

type Frame = 'front' | 'back' | 'walk1' | 'walk2' | 'dive';
const FRAMES: Frame[] = ['front', 'back', 'walk1', 'walk2', 'dive'];
const PX_PER_M = 320 / 1.75; // sprites are cut at 320 px for a 1.75 m person
const SIDEWALK = 10; // distance of the walking line from the street centreline

interface Kind { frames: Record<Frame, THREE.Texture>; size: Record<Frame, [number, number]> }

interface Ped {
  kind: Kind;
  mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>;
  shadow: THREE.Mesh;
  axis: 'x' | 'z';
  line: number; // street centreline
  side: 1 | -1; // which sidewalk
  dir: 1 | -1;
  s: number;
  speed: number;
  phase: number;
  state: 'walk' | 'dive' | 'down';
  t: number;
  pos: THREE.Vector3;
  vel: THREE.Vector3;
  diveDir: THREE.Vector3;
}

export interface PedEvents { dives: THREE.Vector3[]; closeCalls: number }

export class Pedestrians {
  private peds: Ped[] = [];
  private clock = 0;
  private shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22, depthWrite: false });
  private shadowGeo = new THREE.CircleGeometry(0.45, 16).rotateX(-Math.PI / 2);

  static async load(scene: THREE.Scene, count = 70): Promise<Pedestrians> {
    const meta: Record<string, Record<Frame, [number, number]>> = await (await fetch('/sprites/sprites.json')).json();
    const loader = new THREE.TextureLoader();
    const kinds: Kind[] = await Promise.all(Object.entries(meta).map(async ([id, size]) => {
      const frames = {} as Record<Frame, THREE.Texture>;
      await Promise.all(FRAMES.map(async (f) => {
        const tex = await loader.loadAsync(`/sprites/${id}-${f}.png`);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.anisotropy = 4;
        frames[f] = tex;
      }));
      return { frames, size };
    }));
    return new Pedestrians(scene, kinds, count);
  }

  private constructor(scene: THREE.Scene, kinds: Kind[], count: number) {
    const r = rng(31);
    // Origin at the feet, centred, so scaling a frame keeps the person standing on the ground.
    const geo = new THREE.PlaneGeometry(1, 1).translate(0, 0.5, 0);
    for (let k = 0; k < count; k++) {
      const kind = kinds[k % kinds.length];
      const mat = new THREE.MeshBasicMaterial({ map: kind.frames.front, alphaTest: 0.5, side: THREE.DoubleSide });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.layers.set(CHARACTER_LAYER);
      const shadow = new THREE.Mesh(this.shadowGeo, this.shadowMat);
      scene.add(mesh, shadow);
      this.peds.push({
        kind, mesh, shadow,
        axis: r() < 0.5 ? 'x' : 'z',
        line: -HALF + (1 + Math.floor(r() * (N - 1))) * CELL,
        side: r() < 0.5 ? 1 : -1,
        dir: r() < 0.5 ? 1 : -1,
        s: -HALF + r() * 2 * HALF,
        speed: 1.1 + r() * 0.6,
        phase: r() * 10,
        state: 'walk', t: 0,
        pos: new THREE.Vector3(), vel: new THREE.Vector3(), diveDir: new THREE.Vector3(),
      });
    }
  }

  private walkPos(p: Ped, out: THREE.Vector3) {
    if (p.axis === 'z') out.set(p.line + p.side * SIDEWALK, 0, p.s);
    else out.set(p.s, 0, p.line + p.side * SIDEWALK);
    out.y = groundAt(out.x, out.z, false);
    return out;
  }

  reset() {
    for (const p of this.peds) { p.state = 'walk'; p.t = 0; }
  }

  update(dt: number, car: Car, camera: THREE.Camera): PedEvents {
    this.clock += dt;
    const ev: PedEvents = { dives: [], closeCalls: 0 };
    const fwd = car.fwd;
    const camRight = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    for (const p of this.peds) {
      if (p.state === 'walk') {
        p.s += p.dir * p.speed * dt;
        if (p.s > HALF + 4) p.s = -HALF - 4;
        if (p.s < -HALF - 4) p.s = HALF + 4;
        this.walkPos(p, p.pos);
        // Danger check: is the cab heading straight at me, fast?
        const dx = p.pos.x - car.pos.x, dz = p.pos.z - car.pos.z;
        const ahead = dx * fwd.x + dz * fwd.y;
        const lateral = dx * fwd.y - dz * fwd.x; // + means to the cab's left
        const speed = car.speed;
        if (speed > 7 && ahead > 0 && ahead < 6 + speed * 0.45 && Math.abs(lateral) < 2.8 && Math.abs(p.pos.y - car.pos.y) < 3) {
          // Leap sideways, away from the cab's path.
          const away = Math.abs(lateral) < 0.3 ? (Math.random() < 0.5 ? 1 : -1) : Math.sign(lateral);
          p.diveDir.set(fwd.y * away, 0, -fwd.x * away);
          p.vel.copy(p.diveDir).multiplyScalar(6.5).setY(4.5);
          p.state = 'dive';
          p.t = 0;
          ev.dives.push(p.pos.clone());
        }
      } else if (p.state === 'dive') {
        p.t += dt;
        p.vel.y -= 22 * dt;
        p.pos.addScaledVector(p.vel, dt);
        const g = groundAt(p.pos.x, p.pos.z, false);
        if (p.pos.y <= g && p.t > 0.1) {
          p.pos.y = g;
          p.state = 'down';
          p.t = 0;
          if (Math.hypot(p.pos.x - car.pos.x, p.pos.z - car.pos.z) < 6) ev.closeCalls++;
        }
      } else {
        p.t += dt;
        // Get up and walk back to the sidewalk line.
        if (p.t > 1.1) {
          const home = this.walkPos(p, new THREE.Vector3());
          p.pos.lerp(home, Math.min(1, dt * 3));
          p.pos.y = groundAt(p.pos.x, p.pos.z, false);
          if (p.pos.distanceTo(home) < 0.2) p.state = 'walk';
        }
      }
      this.draw(p, camera, camRight);
    }
    return ev;
  }

  private draw(p: Ped, camera: THREE.Camera, camRight: THREE.Vector3) {
    const { mesh, shadow, kind } = p;
    const cam = camera.position;
    mesh.position.copy(p.pos);
    // Turn to face the camera, upright (a cylindrical billboard).
    mesh.rotation.set(0, Math.atan2(cam.x - p.pos.x, cam.z - p.pos.z), 0);
    let frame: Frame;
    let flip = false;
    if (p.state === 'dive' || p.state === 'down') {
      frame = 'dive';
      flip = p.diveDir.dot(camRight) < 0; // the drawing leaps to the right
      if (p.state === 'down') mesh.position.y -= 0.2;
    } else {
      const heading = p.axis === 'z' ? new THREE.Vector3(0, 0, p.dir) : new THREE.Vector3(p.dir, 0, 0);
      const toCam = new THREE.Vector3(cam.x - p.pos.x, 0, cam.z - p.pos.z).normalize();
      const c = heading.dot(toCam);
      if (c > 0.72) frame = 'front';
      else if (c < -0.72) frame = 'back';
      else {
        frame = Math.floor((this.clock + p.phase) / 0.27) % 2 ? 'walk1' : 'walk2';
        flip = heading.dot(camRight) < 0; // side drawings walk to the right
      }
      if (frame === 'front' || frame === 'back') mesh.position.y += Math.abs(Math.sin((this.clock + p.phase) * 11)) * 0.04;
    }
    const [w, h] = kind.size[frame];
    mesh.scale.set((w / PX_PER_M) * (flip ? -1 : 1), h / PX_PER_M, 1);
    if (mesh.material.map !== kind.frames[frame]) {
      mesh.material.map = kind.frames[frame];
      mesh.material.needsUpdate = true;
    }
    shadow.position.set(p.pos.x, groundAt(p.pos.x, p.pos.z, false) + 0.04, p.pos.z);
  }
}
