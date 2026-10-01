import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { toon } from './look';

// The SF street kit (assets/blender/street_kit.py): trees, lamps, poles, shelters
// and the cable car, loaded once and drawn as instanced meshes.

export const kit: Partial<Record<string, THREE.Object3D>> = {};
const KIT = ['tree_plane', 'tree_cypress', 'tree_palm', 'street_lamp', 'trolley_pole', 'utility_pole',
  'muni_shelter', 'bench', 'planter', 'fire_hydrant', 'cable_car', 'cable_car_track'];

export async function loadStreetKit() {
  const loader = new GLTFLoader();
  await Promise.all(KIT.map(async (id) => {
    try {
      const gltf = await loader.loadAsync(`/models/street/${id}.glb`);
      gltf.scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (!mesh.isMesh) return;
        const src = mesh.material as THREE.MeshStandardMaterial;
        mesh.material = src.name.startsWith('light_') ? new THREE.MeshBasicMaterial({ color: src.color }) : toon({ color: src.color });
      });
      gltf.scene.updateMatrixWorld(true);
      kit[id] = gltf.scene;
    } catch (err) {
      console.warn(`No street kit ${id}:`, err);
    }
  }));
}

export interface Part { geometry: THREE.BufferGeometry; material: THREE.Material; local: THREE.Matrix4 }

// Every mesh in a model, with its transform relative to the model's root.
export function partsOf(template: THREE.Object3D): Part[] {
  const parts: Part[] = [];
  const inv = new THREE.Matrix4().copy(template.matrixWorld).invert();
  template.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    parts.push({ geometry: mesh.geometry, material: mesh.material as THREE.Material, local: new THREE.Matrix4().multiplyMatrices(inv, mesh.matrixWorld) });
  });
  return parts;
}

// One instanced mesh per part, placed at each of the given transforms.
export function instance(template: THREE.Object3D, matrices: THREE.Matrix4[], shadows = true) {
  const group = new THREE.Group();
  const parts = partsOf(template);
  const meshes = parts.map((p) => {
    const inst = new THREE.InstancedMesh(p.geometry, p.material, Math.max(1, matrices.length));
    const m = new THREE.Matrix4();
    matrices.forEach((mm, i) => inst.setMatrixAt(i, m.multiplyMatrices(mm, p.local)));
    inst.count = matrices.length;
    inst.castShadow = shadows;
    inst.receiveShadow = true;
    inst.frustumCulled = false;
    group.add(inst);
    return inst;
  });
  return { group, meshes, locals: parts.map((p) => p.local) };
}

// Points where the poles' wires attach, relative to the pole's base.
export function wirePoints(id: 'trolley_pole' | 'utility_pole'): THREE.Vector3[] {
  const t = kit[id];
  if (!t) return [new THREE.Vector3(0, id === 'trolley_pole' ? 8.6 : 9.6, 0)];
  const pts: THREE.Vector3[] = [];
  const inv = new THREE.Matrix4().copy(t.matrixWorld).invert();
  t.traverse((o) => { if (o.name.startsWith('wire')) pts.push(o.getWorldPosition(new THREE.Vector3()).applyMatrix4(inv)); });
  return pts.length ? pts : [new THREE.Vector3(0, 8.6, 0)];
}

// A sagging wire between two points, as line segments.
export function sag(a: THREE.Vector3, b: THREE.Vector3, out: number[], droop = 0.35, steps = 8) {
  const len = a.distanceTo(b);
  let prev = a;
  for (let k = 1; k <= steps; k++) {
    const t = k / steps;
    const p = a.clone().lerp(b, t);
    p.y -= Math.sin(t * Math.PI) * droop * (len / 30);
    out.push(prev.x, prev.y, prev.z, p.x, p.y, p.z);
    prev = p;
  }
}
