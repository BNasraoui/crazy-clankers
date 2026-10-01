import * as THREE from 'three';
import { gltfLoader } from './scenery';
import { toon } from './look';
import { makeCharacter } from './anime';

const lam = (color: THREE.ColorRepresentation) => toon(color);
const glow = (color: THREE.ColorRepresentation) => new THREE.MeshBasicMaterial({ color });

function box(w: number, h: number, d: number, mat: THREE.Material, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  return m;
}

export interface CarModel {
  root: THREE.Group; // position + yaw
  body: THREE.Group; // pitch + roll
  wheels: THREE.Object3D[];
  steer: THREE.Object3D[]; // front wheel pivots
  spinner?: THREE.Object3D;
}

function addWheels(body: THREE.Group, halfW: number, front: number, back: number, r = 0.42): Pick<CarModel, 'wheels' | 'steer'> {
  const tire = lam(0x151515);
  const hub = lam(0x9a9a9a);
  const wheels: THREE.Mesh[] = [];
  const steer: THREE.Group[] = [];
  for (const [x, z] of [[-halfW, front], [halfW, front], [-halfW, back], [halfW, back]]) {
    const pivot = new THREE.Group();
    pivot.position.set(x, r, z);
    const w = new THREE.Mesh(new THREE.CylinderGeometry(r, r, 0.34, 10), tire);
    w.rotation.z = Math.PI / 2;
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.5, r * 0.5, 0.36, 6), hub);
    w.add(cap);
    pivot.add(w);
    body.add(pivot);
    wheels.push(w);
    if (z === front) steer.push(pivot);
  }
  return { wheels, steer };
}

// Blender-built passengers, keyed by passenger id. Passengers are drawn as sprites now, so none are
// loaded (the Tech Bro model lives in assets/models); without a sprite they fall back to box people.
export async function loadPeople(): Promise<Partial<Record<string, THREE.Object3D>>> {
  return {};
}

export function personFrom(template: THREE.Object3D): PersonModel {
  const root = new THREE.Group();
  const body = template.clone(true);
  root.add(body);
  const part = (name: string) => body.getObjectByName(name) ?? new THREE.Object3D();
  return { root, armL: part('arm_L'), armR: part('arm_R'), raise: 0.3 };
}

// Playable robotaxis, built in Blender (assets/blender/). Each glb has nodes
// body, wheel_FL/FR/RL/RR and optionally lidar.
export interface CabInfo { id: string; name: string; tagline: string }
export const CABS: CabInfo[] = [
  { id: 'wayfarer', name: 'WAYFARER', tagline: 'Jaguar-based. Sensors everywhere. Apologises a lot.' },
  { id: 'cybercab', name: 'CYBER CAB', tagline: 'Two seats, no wheel, delivery date TBC.' },
  { id: 'zoox', name: 'ZOOMBOX', tagline: 'Both ends are the front. No steering wheel. No regrets.' },
  { id: 'apollo', name: 'ARTEMIS GO', tagline: 'Cheapest fare in town. Swaps its own battery. Never sleeps.' },
];
// Cars that can appear in traffic but aren't playable.
export const EXTRA_CARS = ['cab'];

const carTemplates = new Map<string, THREE.Object3D>();

// Per-car colour overrides by material role, applied when the model loads, so each
// brand has its own look regardless of what the Blender export used.
const CAR_PALETTES: Record<string, Record<string, number>> = {
  // The real Cybercab is champagne gold with no livery: hide the accent swoosh in the body colour.
  cybercab: { body: 0xc8b48c, accent: 0xc8b48c, hub: 0x8c7a5c },
};

export async function loadCars(): Promise<void> {
  const loader = gltfLoader();
  await Promise.all([...CABS.map((c) => c.id), ...EXTRA_CARS].map(async (id) => {
    try {
      const gltf = await loader.loadAsync(`/models/${id}.glb`);
      const palette = CAR_PALETTES[id];
      if (palette)
        gltf.scene.traverse((o) => {
          const mat = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
          if (mat && palette[mat.name] !== undefined) mat.color.setHex(palette[mat.name]);
        });
      carTemplates.set(id, gltf.scene);
    } catch (err) {
      console.warn(`No ${id}.glb:`, err);
    }
  }));
}

// A fresh, independently animated instance of a car (player or traffic).
export function makeCar(id: string): CarModel {
  const template = carTemplates.get(id);
  if (!template) {
    const cab = makeCab();
    makeCharacter(cab.root);
    return cab;
  }
  const scene = template.clone(true);
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  body.add(scene);
  makeCharacter(root);
  const node = (name: string) => {
    const o = scene.getObjectByName(name);
    if (o) o.rotation.order = 'YXZ'; // steer about Y, then spin about the axle
    return o;
  };
  const wheels = ['wheel_FL', 'wheel_FR', 'wheel_RL', 'wheel_RR'].map(node).filter((o): o is THREE.Object3D => !!o);
  return { root, body, wheels, steer: wheels.slice(0, 2), spinner: node('lidar') };
}

// The placeholder cab: a polite white robotaxi with a spinning lidar puck.
export function makeCab(): CarModel {
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  const white = lam(0xf3f3ef), glass = lam(0x1c2530), black = lam(0x181818);
  body.add(box(2.1, 0.75, 4.6, white, 0, 0.78, 0));
  body.add(box(1.85, 0.7, 2.5, glass, 0, 1.47, -0.25));
  body.add(box(1.8, 0.08, 2.3, white, 0, 1.85, -0.25));
  body.add(box(2.13, 0.12, 3.9, glow(0x2fe0c8), 0, 0.62, 0));
  body.add(box(0.5, 0.18, 0.08, glow(0xfff6d8), -0.65, 0.95, 2.31));
  body.add(box(0.5, 0.18, 0.08, glow(0xfff6d8), 0.65, 0.95, 2.31));
  body.add(box(0.6, 0.16, 0.08, glow(0xff2a2a), -0.6, 0.95, -2.31));
  body.add(box(0.6, 0.16, 0.08, glow(0xff2a2a), 0.6, 0.95, -2.31));
  // Fender sensors.
  body.add(box(0.22, 0.35, 0.3, black, -1.12, 1.05, 1.6));
  body.add(box(0.22, 0.35, 0.3, black, 1.12, 1.05, 1.6));
  // Lidar puck.
  body.add(box(0.8, 0.14, 0.8, white, 0, 1.96, -0.1));
  const spinner = new THREE.Group();
  spinner.position.set(0, 2.2, -0.1);
  const puck = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.38, 0.38, 12), black);
  const band = new THREE.Mesh(new THREE.CylinderGeometry(0.39, 0.39, 0.08, 12), glow(0x2fe0c8));
  const fin = box(0.08, 0.2, 0.42, glow(0x2fe0c8), 0, 0.22, 0);
  puck.castShadow = true;
  spinner.add(puck, band, fin);
  body.add(spinner);
  return { root, body, spinner, ...addWheels(body, 1.0, 1.5, -1.5) };
}

export function makeSedan(color: THREE.ColorRepresentation): CarModel {
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  body.add(box(2.0, 0.7, 4.4, lam(color), 0, 0.75, 0));
  body.add(box(1.8, 0.65, 2.2, lam(0x26313c), 0, 1.4, -0.2));
  body.add(box(1.75, 0.08, 2.0, lam(color), 0, 1.75, -0.2));
  body.add(box(0.5, 0.15, 0.06, glow(0xff2a2a), -0.6, 0.9, -2.21));
  body.add(box(0.5, 0.15, 0.06, glow(0xff2a2a), 0.6, 0.9, -2.21));
  return { root, body, ...addWheels(body, 0.95, 1.4, -1.4) };
}

// A certain angular stainless pickup.
export function makeWedge(): CarModel {
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  const s = new THREE.Shape();
  s.moveTo(-2.8, 0.45);
  s.lineTo(2.8, 0.45);
  s.lineTo(2.8, 1.15);
  s.lineTo(0.1, 2.05);
  s.lineTo(-2.8, 1.35);
  s.closePath();
  const geo = new THREE.ExtrudeGeometry(s, { depth: 2.2, bevelEnabled: false });
  geo.translate(0, 0, -1.1);
  geo.rotateY(-Math.PI / 2);
  const m = new THREE.Mesh(geo, toon(0xaeb3b6));
  m.castShadow = true;
  body.add(m);
  body.add(box(2.1, 0.08, 0.06, glow(0xffffff), 0, 1.12, 2.82));
  body.add(box(2.1, 0.08, 0.06, glow(0xff2a2a), 0, 1.3, -2.82));
  return { root, body, ...addWheels(body, 1.05, 1.8, -1.8, 0.48) };
}

// The bidirectional toaster robotaxi.
export function makeToaster(): CarModel {
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  body.add(box(2.0, 1.6, 3.6, lam(0xe9e4da), 0, 1.35, 0));
  body.add(box(2.02, 0.7, 3.0, lam(0x1c2530), 0, 1.55, 0));
  for (const z of [-1.8, 1.8]) body.add(box(1.2, 0.12, 0.06, glow(0x9ad8ff), 0, 0.9, z));
  for (const x of [-0.9, 0.9]) for (const z of [-1.7, 1.7]) body.add(box(0.2, 0.25, 0.2, lam(0x181818), x, 2.25, z));
  return { root, body, ...addWheels(body, 0.95, 1.3, -1.3) };
}

export interface PersonSpec { shirt: number; pants: number; hair: number; skin: number; height?: number; longHair?: boolean; vest?: number; glasses?: boolean; curly?: boolean }

// raise: how far the waving arm lifts (radians about Z). Box people wave the whole arm;
// Blender people hold a cup in a bent arm, so they raise it in a small toast instead.
export interface PersonModel { root: THREE.Group; armL: THREE.Object3D; armR: THREE.Object3D; raise: number }

export function makePerson(p: PersonSpec): PersonModel {
  const root = new THREE.Group();
  const s = p.height ?? 1;
  const inner = new THREE.Group();
  inner.scale.setScalar(s);
  root.add(inner);
  inner.add(box(0.28, 0.9, 0.3, lam(p.pants), -0.17, 0.45, 0));
  inner.add(box(0.28, 0.9, 0.3, lam(p.pants), 0.17, 0.45, 0));
  inner.add(box(0.72, 0.85, 0.4, lam(p.shirt), 0, 1.32, 0));
  if (p.vest !== undefined) inner.add(box(0.76, 0.7, 0.44, lam(p.vest), 0, 1.36, 0));
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.5, 0.46), lam(p.skin));
  head.position.y = 2.02;
  head.castShadow = true;
  inner.add(head);
  inner.add(box(0.5, 0.16, 0.5, lam(p.hair), 0, 2.32, -0.02));
  if (p.longHair) inner.add(box(0.5, 0.75, 0.16, lam(p.hair), 0, 1.9, -0.25));
  if (p.curly) for (const [x, z] of [[-0.2, 0.1], [0.2, 0.1], [0, -0.2], [-0.2, -0.2], [0.2, -0.2]])
    inner.add(box(0.24, 0.24, 0.24, lam(p.hair), x, 2.4, z));
  if (p.glasses) inner.add(box(0.48, 0.1, 0.04, lam(0x111111), 0, 2.06, 0.24));
  const arm = (x: number) => {
    const pivot = new THREE.Group();
    pivot.position.set(x, 1.68, 0);
    pivot.add(box(0.2, 0.8, 0.24, lam(p.shirt), 0, -0.38, 0));
    inner.add(pivot);
    return pivot;
  };
  return { root, armL: arm(-0.47), armR: arm(0.47), raise: 2.6 };
}

// Billboard text that always faces the camera.
export function makeLabel(text: string, opts: { bg?: string; fg?: string; height?: number } = {}) {
  const font = '700 56px Bungee, Impact, sans-serif';
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d')!;
  ctx.font = font;
  const w = Math.ceil(ctx.measureText(text).width) + 48;
  c.width = w;
  c.height = 84;
  ctx.font = font;
  ctx.fillStyle = opts.bg ?? '#000000cc';
  ctx.beginPath();
  ctx.roundRect(0, 0, w, 84, 18);
  ctx.fill();
  ctx.fillStyle = opts.fg ?? '#ffffff';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 24, 45);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthWrite: false }));
  const h = opts.height ?? 1.2;
  sprite.scale.set((h * w) / 84, h, 1);
  return sprite;
}
