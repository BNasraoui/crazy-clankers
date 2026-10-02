import * as THREE from 'three';
import { CABS, makeCar, makeLabel, type CarModel } from './models';
import { groundAt } from './features';
import { toon } from './look';

// The robotaxi rank: the title screen and cab picker are staged at a real SF
// curb, where the three cabs queue and the chosen one pulls into the bay.
// A flat stretch of street on Haight-ish x = -64, cabs facing south (+Z), parked
// at the west curb (their right-hand side).

const LINE = -64; // street centreline
const CURB_X = LINE - 5; // parked against the west curb
export const BAY = { x: CURB_X, z: -22, yaw: 0 };
const QUEUE_GAP = 6.6;

interface Slot { model: CarModel; z: number }

export class Rank {
  private cabs: Slot[] = [];
  private group = new THREE.Group();
  private inspectYaw = 0;
  private marker: THREE.Sprite;
  private focusZ = BAY.z;
  private clock = 0;
  selected = 0;

  constructor(private scene: THREE.Scene, selected: number) {
    this.selected = selected;
    // Each cab has a fixed spot in the queue; the camera moves to the one you pick.
    CABS.forEach((c, i) => {
      const model = makeCar(c.id);
      this.group.add(model.root);
      this.cabs.push({ model, z: BAY.z - QUEUE_GAP * i });
    });
    this.focusZ = this.slotZ(selected);
    this.addBay();
    this.marker = makeLabel('▼', { bg: '#00000000', fg: '#ffd23a', height: 0.9 });
    this.group.add(this.marker);
    scene.add(this.group);
  }

  get bayY() { return groundAt(BAY.x, BAY.z); }

  slotZ(i: number) {
    return BAY.z - QUEUE_GAP * i;
  }

  // Where the chosen cab is parked: where the shift starts.
  get start() {
    return { x: CURB_X, z: this.slotZ(this.selected), yaw: BAY.yaw };
  }

  select(i: number) {
    this.selected = (i + CABS.length) % CABS.length;
    this.inspectYaw = 0;
  }

  // look: right-stick / drag input, -1..1. Call every frame while the rank is shown.
  update(dt: number, look: number) {
    this.inspectYaw += look * 2.6 * dt;
    if (look === 0) this.inspectYaw *= Math.exp(-1.5 * dt); // drift back to facing the camera
    this.clock += dt;
    this.cabs.forEach((slot, i) => {
      const { root, spinner } = slot.model;
      root.position.set(CURB_X, groundAt(CURB_X, slot.z), slot.z);
      root.rotation.y = BAY.yaw + (i === this.selected ? this.inspectYaw : 0);
      if (spinner) spinner.rotation.y += dt * 6;
    });
    const z = this.slotZ(this.selected);
    this.focusZ += (z - this.focusZ) * (1 - Math.exp(-6 * dt));
    this.marker.position.set(CURB_X, groundAt(CURB_X, z) + 2.75 + Math.abs(Math.sin(this.clock * 4)) * 0.25, z);
  }

  setVisible(v: boolean) {
    this.group.visible = v;
  }

  // During a shift the parked cabs leave (you drive one of them); the bay and sign stay.
  setCarsVisible(v: boolean) {
    for (const slot of this.cabs) slot.model.root.visible = v;
    this.marker.visible = v;
  }

  // Camera framing: 'wide' for the title, 'picker' for choosing.
  frame(camera: THREE.PerspectiveCamera, mode: 'wide' | 'picker', dt: number) {
    const fz = this.focusZ;
    const y = groundAt(CURB_X, fz);
    const want = mode === 'wide'
      ? { pos: new THREE.Vector3(LINE + 3.5, y + 2.4, BAY.z + 12.5), look: new THREE.Vector3(CURB_X - 0.5, y + 1.6, BAY.z - 6), fov: 58 }
      : { pos: new THREE.Vector3(LINE + 1.2, y + 1.6, fz + 7.2), look: new THREE.Vector3(CURB_X + 2.6, y + 1.0, fz - 1.5), fov: 50 };
    const k = 1 - Math.exp(-4 * dt);
    camera.position.lerp(want.pos, k);
    const lookNow = new THREE.Vector3();
    camera.getWorldDirection(lookNow);
    const target = camera.position.clone().add(lookNow.multiplyScalar(10)).lerp(want.look, k);
    camera.lookAt(target);
    camera.fov += (want.fov - camera.fov) * k;
    camera.updateProjectionMatrix();
  }

  snapCamera(camera: THREE.PerspectiveCamera, mode: 'wide' | 'picker') {
    for (let i = 0; i < 60; i++) this.frame(camera, mode, 0.2);
  }

  // Painted bay with "ROBOTAXI ONLY", plus the rank sign.
  private addBay() {
    const c = document.createElement('canvas');
    c.width = 256;
    c.height = 512;
    const g = c.getContext('2d')!;
    g.strokeStyle = '#ffd23a';
    g.lineWidth = 14;
    g.strokeRect(10, 10, 236, 492);
    g.fillStyle = '#ffd23a';
    g.font = '900 40px Impact, "Arial Black", sans-serif';
    g.textAlign = 'center';
    g.save();
    g.translate(128, 420);
    g.fillText('ROBOTAXI', 0, 0);
    g.fillText('ONLY', 0, 44);
    g.restore();
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    const plain = document.createElement('canvas');
    plain.width = 256;
    plain.height = 512;
    const pg = plain.getContext('2d')!;
    pg.strokeStyle = '#ffd23a';
    pg.lineWidth = 14;
    pg.strokeRect(10, 10, 236, 492);
    const plainTex = new THREE.CanvasTexture(plain);
    plainTex.colorSpace = THREE.SRGBColorSpace;
    CABS.forEach((_, i) => {
      const z = this.slotZ(i);
      const bay = new THREE.Mesh(new THREE.PlaneGeometry(2.8, 5.6), toon({ map: i === 0 ? tex : plainTex, transparent: true, depthWrite: false }));
      bay.rotation.set(-Math.PI / 2, 0, Math.PI); // text reads from the street, towards the camera
      bay.position.set(CURB_X, groundAt(CURB_X, z) + 0.03, z);
      bay.renderOrder = 1;
      this.group.add(bay);
    });

    const signX = LINE - 6.6, signZ = BAY.z - 3.5;
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 3.4, 8), toon({ color: 0x2f5d4f }));
    pole.position.set(signX, groundAt(signX, signZ) + 1.7, signZ);
    const sign = makeLabel('ROBOTAXI RANK', { bg: '#2f6b4f', fg: '#ffffff', height: 0.55 });
    sign.position.set(signX, groundAt(signX, signZ) + 3.2, signZ);
    const sub = makeLabel('NO HUMANS BEYOND THIS POINT', { bg: '#f6f2e7', fg: '#1b1722', height: 0.22 });
    sub.position.set(signX, groundAt(signX, signZ) + 2.75, signZ);
    this.group.add(pole, sign, sub);
  }
}

// Small rendered portraits of each cab for the picker list.
export function snapshotCabs(renderer: THREE.WebGLRenderer, w = 240, h = 132): Record<string, string> {
  const out: Record<string, string> = {};
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(30, w / h, 0.1, 100);
  cam.layers.enableAll();
  cam.position.set(5.2, 2.3, 7.2);
  cam.lookAt(0, 0.8, 0);
  const rt = new THREE.WebGLRenderTarget(w * 2, h * 2);
  rt.texture.colorSpace = THREE.SRGBColorSpace; // so the read-back pixels are display-ready
  const px = new Uint8Array(w * 2 * h * 2 * 4);
  const canvas = document.createElement('canvas');
  canvas.width = w * 2;
  canvas.height = h * 2;
  const ctx = canvas.getContext('2d')!;
  const prevTarget = renderer.getRenderTarget();
  const prevColor = new THREE.Color();
  renderer.getClearColor(prevColor);
  const prevAlpha = renderer.getClearAlpha();
  renderer.setClearColor(0x000000, 0);
  for (const c of CABS) {
    const car = makeCar(c.id);
    car.root.rotation.y = 0;
    scene.add(car.root);
    renderer.setRenderTarget(rt);
    renderer.clear();
    renderer.render(scene, cam);
    renderer.readRenderTargetPixels(rt, 0, 0, w * 2, h * 2, px);
    const img = ctx.createImageData(w * 2, h * 2);
    // WebGL rows are bottom-up.
    for (let y = 0; y < h * 2; y++) img.data.set(px.subarray((h * 2 - 1 - y) * w * 2 * 4, (h * 2 - y) * w * 2 * 4), y * w * 2 * 4);
    ctx.putImageData(img, 0, 0);
    out[c.id] = canvas.toDataURL('image/png');
    scene.remove(car.root);
  }
  renderer.setRenderTarget(prevTarget);
  renderer.setClearColor(prevColor, prevAlpha);
  rt.dispose();
  return out;
}
