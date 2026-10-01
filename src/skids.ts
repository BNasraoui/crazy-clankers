import * as THREE from 'three';
import type { Car } from './car';
import type { Input } from './input';
import { groundAt } from './features';
import { glslColor } from './look';
import { setTyres } from './sfx';

// Tyre marks and burnout smoke, drawn like the rest of the game: marks are
// crisp ink strokes on the road (no blurry decals), smoke is cel-shaded puffs
// with an ink rim that dissolve in a screen-tone dither instead of fading.

const INK = 0x1b1722;
const RUBBER = 0x050407; // darker than the ink, or it vanishes on the asphalt
const MAX_SEGS = 1400; // ring buffer of quads; the oldest marks get recycled
const LIFE = 22; // seconds a mark lasts
const FADE = 6; // ...the last of which it spends fading
const LIFT = 0.04; // above the road, to stay out of its depth

class Marks {
  mesh: THREE.Mesh<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private pos: THREE.BufferAttribute;
  private born: THREE.BufferAttribute;
  private next = 0;
  private dirtyFrom = Infinity;
  private dirtyTo = -1;

  constructor(scene: THREE.Scene) {
    const geo = new THREE.BufferGeometry();
    this.pos = new THREE.BufferAttribute(new Float32Array(MAX_SEGS * 4 * 3), 3).setUsage(THREE.DynamicDrawUsage);
    // x: birth time, y: strength (how hard the tyre was sliding)
    this.born = new THREE.BufferAttribute(new Float32Array(MAX_SEGS * 4 * 2).fill(-1e4), 2).setUsage(THREE.DynamicDrawUsage);
    geo.setAttribute('position', this.pos);
    geo.setAttribute('born', this.born);
    const idx = new Uint16Array(MAX_SEGS * 6);
    for (let i = 0; i < MAX_SEGS; i++) idx.set([i * 4, i * 4 + 1, i * 4 + 2, i * 4 + 1, i * 4 + 3, i * 4 + 2], i * 6);
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    const mat = new THREE.ShaderMaterial({
      uniforms: { uTime: { value: 0 } },
      transparent: true,
      depthWrite: false,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
      side: THREE.DoubleSide,
      vertexShader: /* glsl */ `
        attribute vec2 born;
        uniform float uTime;
        varying float vA;
        void main() {
          float age = uTime - born.x;
          vA = born.y * clamp((${LIFE.toFixed(1)} - age) / ${FADE.toFixed(1)}, 0.0, 1.0);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        varying float vA;
        void main() {
          if (vA <= 0.01) discard;
          gl_FragColor = vec4(${glslColor(RUBBER)}, vA);
          #include <colorspace_fragment>
        }`,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = -0.5;
    scene.add(this.mesh);
  }

  // One quad from the previous edge pair (a0, a1) to the new one (b0, b1).
  add(a0: THREE.Vector3, a1: THREE.Vector3, b0: THREE.Vector3, b1: THREE.Vector3, time: number, strength: number) {
    const i = this.next;
    this.next = (this.next + 1) % MAX_SEGS;
    const p = this.pos.array as Float32Array, b = this.born.array as Float32Array;
    [a0, a1, b0, b1].forEach((v, k) => {
      p.set([v.x, v.y, v.z], (i * 4 + k) * 3);
      b.set([time, strength], (i * 4 + k) * 2);
    });
    this.dirtyFrom = Math.min(this.dirtyFrom, i);
    this.dirtyTo = Math.max(this.dirtyTo, i);
  }

  flush(time: number) {
    this.mesh.material.uniforms.uTime.value = time;
    if (this.dirtyTo < 0) return;
    const n = this.dirtyTo - this.dirtyFrom + 1;
    // Ranges pile up until three.js uploads them on the next render, then it clears them.
    for (const [attr, size] of [[this.pos, 3], [this.born, 2]] as const) {
      attr.addUpdateRange(this.dirtyFrom * 4 * size, n * 4 * size);
      attr.needsUpdate = true;
    }
    this.dirtyFrom = Infinity;
    this.dirtyTo = -1;
  }

  clear() {
    (this.born.array as Float32Array).fill(-1e4);
    this.born.clearUpdateRanges();
    this.born.needsUpdate = true;
  }
}

const MAX_PUFFS = 90;
const PUFF_LIFE = 1.5;

class Smoke {
  points: THREE.Points<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private pos: THREE.BufferAttribute;
  private data: THREE.BufferAttribute; // birth, size, seed
  private vel: THREE.Vector3[] = [];
  private next = 0;
  private live = 0;

  constructor(scene: THREE.Scene) {
    const geo = new THREE.BufferGeometry();
    this.pos = new THREE.BufferAttribute(new Float32Array(MAX_PUFFS * 3), 3).setUsage(THREE.DynamicDrawUsage);
    this.data = new THREE.BufferAttribute(new Float32Array(MAX_PUFFS * 3).fill(-1e4), 3).setUsage(THREE.DynamicDrawUsage);
    geo.setAttribute('position', this.pos);
    geo.setAttribute('puff', this.data);
    for (let i = 0; i < MAX_PUFFS; i++) this.vel.push(new THREE.Vector3());
    const mat = new THREE.ShaderMaterial({
      uniforms: { uTime: { value: 0 }, uPx: { value: 720 } },
      // Drawn after the opaque world, without writing depth: the look's depth
      // outlines would otherwise ink every dissolving pixel.
      transparent: true,
      depthWrite: false,
      vertexShader: /* glsl */ `
        attribute vec3 puff;
        uniform float uTime, uPx;
        varying float vAge, vSeed;
        void main() {
          vAge = (uTime - puff.x) / ${PUFF_LIFE.toFixed(2)};
          vSeed = puff.z;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_Position = projectionMatrix * mv;
          float size = puff.y * (0.45 + 0.75 * sqrt(clamp(vAge, 0.0, 1.0)));
          // Capped, so a puff drifting past the camera never blots out the road.
          gl_PointSize = vAge < 0.0 || vAge > 1.0 ? 0.0 : min(size * projectionMatrix[1][1] * uPx * 0.5 / -mv.z, uPx * 0.09);
        }`,
      fragmentShader: /* glsl */ `
        varying float vAge, vSeed;
        void main() {
          vec2 uv = gl_PointCoord * 2.0 - 1.0;
          uv.y = -uv.y;
          float a = atan(uv.y, uv.x);
          // A lumpy cloud outline, different for every puff.
          float edge = 0.8 + 0.08 * sin(a * 5.0 + vSeed * 6.3) + 0.05 * sin(a * 9.0 - vSeed * 4.1);
          float r = length(uv) / edge;
          if (r > 1.0) discard;
          // Screen-tone dissolve: crisp pixels drop out as the puff ages.
          vec2 cell = floor(gl_FragCoord.xy / 2.0);
          float dither = fract(sin(dot(cell, vec2(12.9898, 78.233)) + vSeed) * 43758.5453);
          if (dither < vAge * vAge * 1.1 - 0.05) discard;
          vec3 n = vec3(uv / edge, sqrt(max(0.0, 1.0 - r * r)));
          float lit = dot(n, normalize(vec3(-0.5, 0.65, 0.55)));
          vec3 col = lit > 0.05 ? vec3(0.95, 0.94, 0.92) : vec3(0.71, 0.70, 0.78);
          if (r > 0.88) col = ${glslColor(INK)};
          gl_FragColor = vec4(col, 1.0);
          #include <colorspace_fragment>
        }`,
    });
    this.points = new THREE.Points(geo, mat);
    this.points.frustumCulled = false;
    // Size the puffs for whatever target the look is rendering into (it renders at a low resolution).
    this.points.onBeforeRender = (renderer) => {
      mat.uniforms.uPx.value = renderer.getRenderTarget()?.height ?? renderer.domElement.height;
    };
    scene.add(this.points);
  }

  emit(at: THREE.Vector3, drift: THREE.Vector3, time: number, size: number) {
    const i = this.next;
    this.next = (this.next + 1) % MAX_PUFFS;
    this.pos.setXYZ(i, at.x + (Math.random() - 0.5) * 0.4, at.y + 0.3, at.z + (Math.random() - 0.5) * 0.4);
    this.data.setXYZ(i, time, size * (0.8 + Math.random() * 0.4), Math.random());
    this.vel[i].set(drift.x + (Math.random() - 0.5) * 1.5, 1.1 + Math.random() * 0.8, drift.z + (Math.random() - 0.5) * 1.5);
    this.data.needsUpdate = true;
    this.live = PUFF_LIFE;
  }

  update(dt: number, time: number) {
    this.points.material.uniforms.uTime.value = time;
    if (this.live <= 0) return; // nothing on screen, nothing to move
    this.live -= dt;
    const p = this.pos.array as Float32Array;
    const drag = Math.exp(-2.2 * dt);
    for (let i = 0; i < MAX_PUFFS; i++) {
      const v = this.vel[i];
      v.multiplyScalar(drag);
      p[i * 3] += v.x * dt;
      p[i * 3 + 1] += (v.y + 0.5) * dt;
      p[i * 3 + 2] += v.z * dt;
    }
    this.pos.needsUpdate = true;
  }

  clear() {
    (this.data.array as Float32Array).fill(-1e4);
    this.data.needsUpdate = true;
  }
}

interface Wheel {
  local: THREE.Vector2; // x right, y forward (car space)
  rear: boolean;
  down: boolean; // currently laying a mark
  l: THREE.Vector3; // last edge pair
  r: THREE.Vector3;
  last: THREE.Vector3; // centre at the last edge
  scrubT: number; // burnout-in-place timer
}

const HALF_W = 0.82, AXLE = 1.3; // fallback wheel layout

// Works out how hard each tyre is sliding and turns that into marks, smoke and squeal.
export class Tyres {
  private marks: Marks;
  private smoke: Smoke;
  private wheels: Wheel[] = [];
  private model: unknown = null;
  private time = 0;
  private prevCharge = 0;
  private launchT = 0; // wheelspin left over after a launch
  private puffT = 0;
  private slip = 0;
  private tmp = new THREE.Vector3();

  constructor(scene: THREE.Scene) {
    this.marks = new Marks(scene);
    this.smoke = new Smoke(scene);
  }

  reset() {
    this.marks.clear();
    this.smoke.clear();
    for (const w of this.wheels) w.down = false;
    this.launchT = this.prevCharge = this.slip = 0;
  }

  // Read the wheel layout off the cab model (it changes when you pick another cab).
  private layout(car: Car) {
    if (this.model === car.model) return;
    this.model = car.model;
    const root = car.model.root;
    root.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
    let pts = car.model.wheels.map((w) => w.getWorldPosition(new THREE.Vector3()).applyMatrix4(inv));
    if (pts.length < 4 || pts.some((p) => !Number.isFinite(p.x)) || Math.max(...pts.map((p) => Math.abs(p.x))) < 0.3)
      pts = [[-1, 1], [1, 1], [-1, -1], [1, -1]].map(([x, z]) => new THREE.Vector3(x * HALF_W, 0, z * AXLE));
    // Four corners: the outermost wheel on each side of each axle.
    const front = pts.filter((p) => p.z >= 0), back = pts.filter((p) => p.z < 0);
    const corners: [THREE.Vector3, boolean][] = [];
    for (const [set, rear] of [[front, false], [back, true]] as const)
      for (const side of [-1, 1]) {
        const s = set.filter((p) => Math.sign(p.x) === side);
        if (s.length) corners.push([s.reduce((a, b) => (Math.abs(b.z) > Math.abs(a.z) ? b : a)), rear]);
      }
    this.wheels = corners.map(([p, rear]) => ({
      local: new THREE.Vector2(p.x, p.z), rear, down: false,
      l: new THREE.Vector3(), r: new THREE.Vector3(), last: new THREE.Vector3(), scrubT: 0,
    }));
  }

  update(dt: number, car: Car, inp: Input, playing: boolean) {
    this.time += dt;
    this.layout(car);
    const vf = car.forward, lat = Math.abs(car.lateral), speed = car.speed;
    let rear = 0, front = 0, spin = 0;
    if (playing && car.grounded && !car.underwater) {
      const sideways = THREE.MathUtils.clamp((lat - 2.5) / 7, 0, 1);
      // Launch Mode: handbrake + gas spins the rears; a launch keeps them spinning a moment.
      if (car.launchCharge > 0) spin = 1;
      else if (this.prevCharge >= 0.35 && inp.throttle > 0.5) this.launchT = 0.55;
      if (this.launchT > 0) {
        spin = Math.max(spin, this.launchT / 0.55);
        this.launchT -= dt;
      }
      // Flooring it from a crawl chirps the tyres a little.
      if (inp.throttle > 0.9 && vf > -0.5 && vf < 7) spin = Math.max(spin, 0.4 * (1 - vf / 7));
      const braking = inp.brake > 0.4 && vf > 6 ? inp.brake * Math.min(1, vf / 22) : 0;
      const handbrake = inp.handbrake && speed > 6 && car.launchCharge === 0 ? 0.55 : 0;
      rear = Math.max(sideways, spin, braking * 0.85, handbrake);
      front = Math.max(sideways * 0.7, braking);
    }
    this.prevCharge = car.launchCharge;
    const target = Math.max(rear, front);
    this.slip += (target - this.slip) * (1 - Math.exp(-12 * dt));
    setTyres(this.slip, spin, speed, inp.throttle, playing);

    // Marks and smoke, wheel by wheel.
    const fx = Math.sin(car.yaw), fz = Math.cos(car.yaw);
    const rx = -fz, rz = fx; // car's right
    const drift = new THREE.Vector3(-fx * Math.min(speed, 6) * 0.15, 0, -fz * Math.min(speed, 6) * 0.15);
    this.puffT -= dt;
    const puff = playing && (spin > 0.5 || (rear > 0.8 && speed > 12)) && this.puffT <= 0;
    if (puff) this.puffT = spin > 0.5 ? 0.06 : 0.14;
    for (const w of this.wheels) {
      const s = w.rear ? rear : front;
      const on = s > (w.rear ? 0.3 : 0.5);
      // The wheel's centre on the ground (local x is to the car's left in three.js space, so flip it).
      const cx = car.pos.x - rx * w.local.x + fx * w.local.y;
      const cz = car.pos.z - rz * w.local.x + fz * w.local.y;
      const gy = groundAt(cx, cz, false);
      const onRoad = Math.abs(gy - car.pos.y) < 0.6; // not on a carrier's ramp or mid-air
      if (!on || !onRoad) {
        w.down = false;
        continue;
      }
      const width = 0.14 + 0.18 * s; // pressure on the brush
      const c = this.tmp.set(cx, gy + LIFT, cz);
      if (!w.down) {
        w.down = true;
        edges(c, fx, fz, width, w.l, w.r);
        w.last.copy(c);
        w.scrubT = 0;
      } else if (c.distanceToSquared(w.last) > 0.45 * 0.45) {
        const l = new THREE.Vector3(), r = new THREE.Vector3();
        // Edges across the direction of travel, so sideways slides still draw a clean band.
        const dx = c.x - w.last.x, dz = c.z - w.last.z, d = Math.hypot(dx, dz);
        edges(c, dx / d, dz / d, width, l, r);
        this.marks.add(w.l, w.r, l, r, this.time, Math.min(0.95, 0.5 + s * 0.5));
        w.l.copy(l);
        w.r.copy(r);
        w.last.copy(c);
      } else if (w.rear && spin > 0.8 && (w.scrubT -= dt) <= 0) {
        // Burnout on the spot: smear short strokes back and forth into a black patch.
        w.scrubT = 0.12;
        const j = (Math.random() - 0.5) * 0.12;
        const a = new THREE.Vector3(cx - fx * 0.45 + rx * j, gy + LIFT, cz - fz * 0.45 + rz * j);
        const b = new THREE.Vector3(cx + fx * 0.25 + rx * j, gy + LIFT, cz + fz * 0.25 + rz * j);
        const al = new THREE.Vector3(), ar = new THREE.Vector3(), bl = new THREE.Vector3(), br = new THREE.Vector3();
        edges(a, fx, fz, 0.26, al, ar);
        edges(b, fx, fz, 0.26, bl, br);
        this.marks.add(al, ar, bl, br, this.time, 0.35);
      }
      if (puff && w.rear) this.smoke.emit(c, drift, this.time, spin > 0.5 ? 1.25 : 0.85);
    }
    this.marks.flush(this.time);
    this.smoke.update(dt, this.time);
  }
}

// Left/right edge points of a stroke centred on c, heading (dx, dz).
function edges(c: THREE.Vector3, dx: number, dz: number, width: number, l: THREE.Vector3, r: THREE.Vector3) {
  const h = width / 2;
  l.set(c.x - dz * h, 0, c.z + dx * h);
  r.set(c.x + dz * h, 0, c.z - dx * h);
  l.y = groundAt(l.x, l.z, false) + LIFT;
  r.y = groundAt(r.x, r.z, false) + LIFT;
}
