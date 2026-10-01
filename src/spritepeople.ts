import * as THREE from 'three';
import { CHARACTER_LAYER } from './anime';
import type { PersonModel } from './models';

// Passengers drawn as 2D anime sprites standing in the 3D world, like the
// pedestrians: always facing the camera, showing the drawing for the viewing angle.
// Frames per passenger: front, wave1, wave2 (hailing a taxi), side, back.

type Frame = 'front' | 'wave1' | 'wave2' | 'side' | 'back';
const PX_PER_M = 320 / 1.75; // sheets are cut at 320 px for a 1.75 m person

export interface SpriteSet { frames: Partial<Record<Frame, THREE.Texture>>; size: Partial<Record<Frame, [number, number]>> }

export async function loadPassengerSprites(): Promise<Record<string, SpriteSet>> {
  const res = await fetch('/sprites/passengers.json');
  if (!res.ok) return {};
  const meta: Record<string, Partial<Record<Frame, [number, number]>>> = await res.json();
  const loader = new THREE.TextureLoader();
  const out: Record<string, SpriteSet> = {};
  await Promise.all(Object.entries(meta).map(async ([id, size]) => {
    const frames: Partial<Record<Frame, THREE.Texture>> = {};
    await Promise.all((Object.keys(size) as Frame[]).map(async (f) => {
      const tex = await loader.loadAsync(`/sprites/pax-${id}-${f}.png`);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 4;
      frames[f] = tex;
    }));
    out[id] = { frames, size };
  }));
  return out;
}

const geo = new THREE.PlaneGeometry(1, 1).translate(0, 0.5, 0);
const shadowGeo = new THREE.CircleGeometry(0.42, 16).rotateX(-Math.PI / 2);
const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22, depthWrite: false });

export class SpritePerson implements PersonModel {
  root = new THREE.Group();
  armL = new THREE.Object3D();
  armR = new THREE.Object3D();
  raise = 0;
  hailing = true;
  private mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>;
  private phase = Math.random() * 10;

  constructor(private set: SpriteSet) {
    this.mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: set.frames.front ?? null, alphaTest: 0.5, side: THREE.DoubleSide }));
    this.mesh.layers.set(CHARACTER_LAYER);
    const shadow = new THREE.Mesh(shadowGeo, shadowMat);
    shadow.position.y = 0.04;
    this.root.add(this.mesh, shadow);
  }

  // facing: yaw the person faces (towards the street). size: the people-size setting.
  tick(camera: THREE.Camera, clock: number, size: number) {
    const p = this.root.getWorldPosition(new THREE.Vector3());
    const cam = camera.position;
    // Undo the root's own yaw, then face the camera.
    const toCamYaw = Math.atan2(cam.x - p.x, cam.z - p.z);
    this.mesh.rotation.y = toCamYaw - this.root.rotation.y;
    const heading = new THREE.Vector3(Math.sin(this.root.rotation.y), 0, Math.cos(this.root.rotation.y));
    const toCam = new THREE.Vector3(cam.x - p.x, 0, cam.z - p.z).normalize();
    const c = heading.dot(toCam);
    const camRight = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    let frame: Frame;
    let flip = false;
    if (c > 0.55) {
      // The two hailing drawings raise opposite arms; mirroring the second keeps one arm up, waving side to side.
      const second = Math.floor((clock + this.phase) / 0.22) % 2 === 1;
      frame = this.hailing && this.set.frames.wave1 ? (second ? 'wave2' : 'wave1') : 'front';
      flip = frame === 'wave2';
    }
    else if (c < -0.55) frame = 'back';
    else {
      frame = 'side';
      flip = heading.dot(camRight) < 0; // the side drawing faces right
    }
    const tex = this.set.frames[frame] ?? this.set.frames.front!;
    const [w, h] = this.set.size[frame] ?? this.set.size.front!;
    const k = size / PX_PER_M;
    this.mesh.scale.set(w * k * (flip ? -1 : 1), h * k, 1);
    if (this.mesh.material.map !== tex) {
      this.mesh.material.map = tex;
      this.mesh.material.needsUpdate = true;
    }
  }
}
