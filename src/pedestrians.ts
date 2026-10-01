import * as THREE from 'three';
import { CHARACTER_LAYER } from './anime';
import { groundAt } from './features';
import { CELL, HALF, N, STREET_HALF, rng } from './world';
import type { Car } from './car';

// Pedestrians are 2D sprites standing in the 3D world (like Paper Mario or
// Octopath Traveler). Each one always turns to face the camera and shows the
// drawing that matches the viewing angle: front, back, or a side walk cycle.
// They always dive out of the way; nobody gets run over in Crazy Clankers.

type Frame = 'front' | 'back' | 'walk1' | 'walk2' | 'dive'
  | 'fwalk1' | 'fwalk2' | 'bwalk1' | 'bwalk2' | 'swalk1' | 'swalk2' | 'swalk3' | 'swalk4';
const PX_PER_M = 320 / 1.75; // sprites are cut at 320 px for a 1.75 m person
const SIDEWALK = 7.9; // walking line, just past the street trees, measured from the street centreline

interface Kind { id: string; frames: Partial<Record<Frame, THREE.Texture>>; size: Partial<Record<Frame, [number, number]>> }

// Walk cycles per view, falling back to whatever frames a sprite set has.
const CYCLES: Record<'front' | 'back' | 'side', Frame[][]> = {
  front: [['fwalk1', 'fwalk2'], ['front']],
  back: [['bwalk1', 'bwalk2'], ['back']],
  side: [['swalk1', 'swalk2', 'swalk3', 'swalk4'], ['walk1', 'walk2']],
};
const STEP_TIME: Record<number, number> = { 1: 1, 2: 0.26, 4: 0.15 };

interface Ped {
  kind: Kind;
  mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>;
  shadow: THREE.Mesh;
  axis: 'x' | 'z';
  line: number; // street centreline
  side: 1 | -1; // which sidewalk
  dir: 1 | -1;
  s: number;
  cross?: { at: number; min: number; max: number; wait: number }; // crosswalk walkers go back and forth
  speed: number;
  phase: number;
  state: 'walk' | 'alert' | 'dive' | 'down';
  alert: THREE.Sprite;
  t: number;
  pos: THREE.Vector3;
  vel: THREE.Vector3;
  diveDir: THREE.Vector3;
  shoutAt: number; // clock time before which this person stays quiet
}

export interface PedEvents { dives: THREE.Vector3[]; closeCalls: number }
// Someone reacting out loud to the cab, for src/voices.ts. pos is live: it follows them.
export interface Shout { pos: THREE.Vector3; kind: string; scream: boolean }

// A manga "!" that pops over someone's head when they spot the cab.
function alertTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d')!;
  g.translate(64, 64);
  g.fillStyle = '#ffd23a';
  g.strokeStyle = '#1b1722';
  g.lineWidth = 8;
  g.beginPath();
  for (let k = 0; k < 20; k++) {
    const a = (k / 20) * Math.PI * 2, r = k % 2 ? 40 : 58;
    g.lineTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  g.closePath();
  g.fill();
  g.stroke();
  g.font = '900 72px Impact, "Arial Black", sans-serif';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.lineWidth = 10;
  g.strokeText('!', 0, 4);
  g.fillStyle = '#ff4a3a';
  g.fillText('!', 0, 4);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
const ALERT_TIME = 0.22;

export class Pedestrians {
  private peds: Ped[] = [];
  private clock = 0;
  shouts: Shout[] = []; // this frame's reactions
  size = 1.3; // drawn larger than life so they read at speed (tunable in the look panel)
  private shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22, depthWrite: false });
  private shadowGeo = new THREE.CircleGeometry(0.45, 16).rotateX(-Math.PI / 2);

  static async load(scene: THREE.Scene, count = 70): Promise<Pedestrians> {
    const meta: Record<string, Partial<Record<Frame, [number, number]>>> = await (await fetch('/sprites/sprites.json')).json();
    const loader = new THREE.TextureLoader();
    const kinds: Kind[] = await Promise.all(Object.entries(meta).map(async ([id, size]) => {
      const frames: Partial<Record<Frame, THREE.Texture>> = {};
      await Promise.all((Object.keys(size) as Frame[]).map(async (f) => {
        const tex = await loader.loadAsync(`/sprites/${id}-${f}.png`);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.anisotropy = 4;
        frames[f] = tex;
      }));
      return { id, frames, size };
    }));
    return new Pedestrians(scene, kinds, count);
  }

  private constructor(scene: THREE.Scene, kinds: Kind[], count: number) {
    const r = rng(31);
    // Origin at the feet, centred, so scaling a frame keeps the person standing on the ground.
    const geo = new THREE.PlaneGeometry(1, 1).translate(0, 0.5, 0);
    // Depth testing stays on: without it WebGL writes no depth, and the look hides character-layer pixels with none.
    const alertMat = new THREE.SpriteMaterial({ map: alertTexture(), alphaTest: 0.5 });
    for (let k = 0; k < count; k++) {
      const kind = kinds[k % kinds.length];
      const mat = new THREE.MeshBasicMaterial({ map: kind.frames.front ?? null, alphaTest: 0.5, side: THREE.DoubleSide });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.layers.set(CHARACTER_LAYER);
      const shadow = new THREE.Mesh(this.shadowGeo, this.shadowMat);
      const alert = new THREE.Sprite(alertMat);
      alert.scale.setScalar(1.1);
      alert.visible = false;
      alert.layers.set(CHARACTER_LAYER);
      alert.renderOrder = 10;
      scene.add(mesh, shadow, alert);
      this.peds.push({
        kind, mesh, shadow,
        axis: r() < 0.5 ? 'x' : 'z',
        line: -HALF + (1 + Math.floor(r() * (N - 1))) * CELL,
        side: r() < 0.5 ? 1 : -1,
        dir: r() < 0.5 ? 1 : -1,
        s: -HALF + r() * 2 * HALF,
        speed: 1.1 + r() * 0.6,
        phase: r() * 10,
        state: 'walk', t: 0, alert,
        pos: new THREE.Vector3(), vel: new THREE.Vector3(), diveDir: new THREE.Vector3(), shoutAt: 0,
      });
      // Every fourth person uses a crosswalk instead of a sidewalk.
      if (k % 4 === 3) {
        const p = this.peds[this.peds.length - 1];
        const street = -HALF + (1 + Math.floor(r() * (N - 1))) * CELL; // the street being crossed
        const corner = -HALF + (1 + Math.floor(r() * (N - 1))) * CELL; // the intersection it's next to
        const at = corner + (r() < 0.5 ? -1 : 1) * (STREET_HALF + 1.5);
        p.cross = { at, min: street - SIDEWALK, max: street + SIDEWALK, wait: r() * 3 };
        p.s = p.cross.min + r() * (p.cross.max - p.cross.min);
      }
    }
  }

  private walkPos(p: Ped, out: THREE.Vector3) {
    if (p.cross) {
      if (p.axis === 'z') out.set(p.cross.at, 0, p.s);
      else out.set(p.s, 0, p.cross.at);
      out.y = groundAt(out.x, out.z, false);
      return out;
    }
    if (p.axis === 'z') out.set(p.line + p.side * SIDEWALK, 0, p.s);
    else out.set(p.s, 0, p.line + p.side * SIDEWALK);
    out.y = groundAt(out.x, out.z, false);
    return out;
  }

  // People out in the road, for traffic to stop for.
  inRoad(): { x: number; z: number }[] {
    const out: { x: number; z: number }[] = [];
    for (const p of this.peds)
      if (p.cross && p.state === 'walk' && Math.abs(p.s - (p.cross.min + p.cross.max) / 2) < STREET_HALF + 1) out.push({ x: p.pos.x, z: p.pos.z });
    return out;
  }

  reset() {
    for (const p of this.peds) { p.state = 'walk'; p.t = 0; p.alert.visible = false; p.shoutAt = 0; }
  }

  update(dt: number, car: Car, camera: THREE.Camera): PedEvents {
    this.clock += dt;
    const ev: PedEvents = { dives: [], closeCalls: 0 };
    this.shouts.length = 0;
    const fwd = car.fwd;
    const camRight = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    for (const p of this.peds) {
      if (p.state === 'walk') {
        if (p.cross) {
          // Wait at the curb, then cross; turn round on the far side.
          if (p.cross.wait > 0) p.cross.wait -= dt;
          else {
            p.s += p.dir * p.speed * dt;
            if (p.s > p.cross.max || p.s < p.cross.min) {
              p.s = Math.min(p.cross.max, Math.max(p.cross.min, p.s));
              p.dir = p.dir === 1 ? -1 : 1;
              p.cross.wait = 2 + Math.random() * 4;
            }
          }
        } else {
          p.s += p.dir * p.speed * dt;
          if (p.s > HALF + 4) p.s = -HALF - 4;
          if (p.s < -HALF - 4) p.s = HALF + 4;
        }
        this.walkPos(p, p.pos);
        // Danger check: is the cab heading straight at me, fast?
        const dx = p.pos.x - car.pos.x, dz = p.pos.z - car.pos.z;
        const ahead = dx * fwd.x + dz * fwd.y;
        const lateral = dx * fwd.y - dz * fwd.x; // + means to the cab's left
        const speed = car.speed;
        if (speed > 7 && ahead > 0 && ahead < 9 + speed * 0.6 && Math.abs(lateral) < 2.8 && Math.abs(p.pos.y - car.pos.y) < 3) {
          // Spot the cab, then leap sideways, away from its path.
          const away = Math.abs(lateral) < 0.3 ? (Math.random() < 0.5 ? 1 : -1) : Math.sign(lateral);
          p.diveDir.set(fwd.y * away, 0, -fwd.x * away);
          p.state = 'alert';
          p.t = 0;
          this.shout(p, true, 6);
        } else if (speed > 6 && Math.hypot(dx, dz) < 5.5 && Math.abs(p.pos.y - car.pos.y) < 2) {
          this.shout(p, false, 8); // the cab tore past on the sidewalk
        }
      } else if (p.state === 'alert') {
        p.t += dt;
        if (p.t > ALERT_TIME) {
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
          p.shoutAt = 0;
          this.shout(p, false, 8); // picking themselves up, furious
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

  private shout(p: Ped, scream: boolean, quiet: number) {
    if (this.clock < p.shoutAt) return;
    p.shoutAt = this.clock + quiet;
    this.shouts.push({ pos: p.pos, kind: p.kind.id, scream });
  }

  private draw(p: Ped, camera: THREE.Camera, camRight: THREE.Vector3) {
    const { mesh, shadow, kind } = p;
    const cam = camera.position;
    mesh.position.copy(p.pos);
    // Turn to face the camera, upright (a cylindrical billboard).
    mesh.rotation.set(0, Math.atan2(cam.x - p.pos.x, cam.z - p.pos.z), 0);
    let frame: Frame;
    let flip = false;
    const pick = (view: 'front' | 'back' | 'side', moving: boolean): Frame => {
      const cycle = CYCLES[view].find((c) => c.every((f) => kind.frames[f])) ?? ['front'];
      if (!moving) return view === 'back' ? (kind.frames.back ? 'back' : cycle[0]) : view === 'front' && kind.frames.front ? 'front' : cycle[0];
      const step = Math.floor((this.clock + p.phase) / (STEP_TIME[cycle.length] ?? 0.2) * (p.speed / 1.4));
      return cycle[step % cycle.length];
    };
    if (p.state === 'dive' || p.state === 'down') {
      frame = 'dive';
      flip = p.diveDir.dot(camRight) < 0; // the drawing leaps to the right
      if (p.state === 'down') mesh.position.y -= 0.2;
    } else {
      const heading = p.axis === 'z' ? new THREE.Vector3(0, 0, p.dir) : new THREE.Vector3(p.dir, 0, 0);
      const toCam = new THREE.Vector3(cam.x - p.pos.x, 0, cam.z - p.pos.z).normalize();
      const c = heading.dot(toCam);
      const moving = p.state === 'walk' && !(p.cross && p.cross.wait > 0);
      if (c > 0.72) frame = pick('front', moving);
      else if (c < -0.72) frame = pick('back', moving);
      else {
        frame = pick('side', moving);
        flip = heading.dot(camRight) < 0; // side drawings walk to the right
      }
    }
    p.alert.visible = p.state === 'alert' || (p.state === 'dive' && p.t < 0.25);
    if (p.alert.visible) {
      const pop = p.state === 'alert' ? Math.min(1, p.t / 0.08) : 1;
      p.alert.position.set(p.pos.x, mesh.position.y + 1.75 * this.size + 0.7, p.pos.z);
      p.alert.scale.setScalar(1.1 * pop);
    }
    const [w, h] = kind.size[frame] ?? kind.size.front!;
    const k = this.size / PX_PER_M;
    mesh.scale.set(w * k * (flip ? -1 : 1), h * k, 1);
    const tex = kind.frames[frame] ?? kind.frames.front!;
    if (mesh.material.map !== tex) {
      mesh.material.map = tex;
      mesh.material.needsUpdate = true;
    }
    shadow.position.set(p.pos.x, groundAt(p.pos.x, p.pos.z, false) + 0.04, p.pos.z);
    shadow.scale.setScalar(this.size);
  }
}
