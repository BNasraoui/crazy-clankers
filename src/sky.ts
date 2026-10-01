import * as THREE from 'three';
import { pool, retry } from './scenery';
import { WATER } from './world';

// The painted sky from the title art: hand-drawn clouds and the Bay's horizons
// (Marin to the north, the Bay Bridge and Oakland to the east, Sutro Tower to the
// south; the west is open ocean). They hang off the sky dome, so they follow the
// camera and read as infinitely far away.

const textures = new Map<string, THREE.Texture>();
const IMAGES = ['horizon-north', 'horizon-east', 'horizon-south', 'cloud-1', 'cloud-2', 'cloud-3'];

export async function loadSky() {
  const loader = new THREE.TextureLoader();
  await pool(IMAGES, 3, async (id) => {
    try {
      const tex = await retry(() => loader.loadAsync(`/sky/${id}.png`));
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 4;
      textures.set(id, tex);
    } catch (err) {
      console.warn(`No sky ${id}:`, err);
    }
  });
}

// Azimuth in degrees, clockwise from north (-z): east is +x.
const dir = (az: number) => { const a = THREE.MathUtils.degToRad(az); return new THREE.Vector3(Math.sin(a), 0, -Math.cos(a)); };

const material = (tex: THREE.Texture) =>
  new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, fog: false, toneMapped: false, side: THREE.DoubleSide });

// A strip of the horizon wrapped around the camera from az0 to az1, shoreline at y = 0.
// `shore` is how far up the image (0..1) the waterline sits; `squash` flattens tall art.
function horizon(tex: THREE.Texture, az0: number, az1: number, shore: number, squash: number, r = 850) {
  const img = tex.image as { width: number; height: number };
  const span = THREE.MathUtils.degToRad(az1 - az0);
  const h = span * r * (img.height / img.width) * squash;
  const y0 = -shore * h;
  const steps = 24, pos: number[] = [], uv: number[] = [], idx: number[] = [];
  for (let k = 0; k <= steps; k++) {
    const t = k / steps, d = dir(az0 + (az1 - az0) * t).multiplyScalar(r);
    pos.push(d.x, y0, d.z, d.x, y0 + h, d.z);
    uv.push(t, 0, t, 1);
    if (k < steps) idx.push(2 * k, 2 * k + 2, 2 * k + 1, 2 * k + 1, 2 * k + 2, 2 * k + 3);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setIndex(idx);
  const mesh = new THREE.Mesh(geo, material(tex));
  mesh.frustumCulled = false;
  return mesh;
}

// Where the clouds sit: image, azimuth, elevation (degrees) and width (m at r = 880).
const CLOUDS: [string, number, number, number][] = [
  ['cloud-1', 20, 14, 420], ['cloud-2', 75, 9, 520], ['cloud-3', 130, 22, 380],
  ['cloud-2', 195, 12, 460], ['cloud-1', 250, 18, 360], ['cloud-3', 300, 8, 420],
  ['cloud-2', 340, 26, 400], ['cloud-3', 50, 34, 300],
];

let clouds: THREE.Group | null = null;
let horizons: THREE.Group | null = null;

export function paintSky(sky: THREE.Object3D) {
  const strips: [string, number, number, number, number][] = [
    ['horizon-north', -38, 40, 0.1, 0.7], ['horizon-east', 35, 145, 0.14, 1], ['horizon-south', 150, 230, 0.05, 0.7],
  ];
  horizons = new THREE.Group();
  for (const [id, a0, a1, shore, squash] of strips) {
    const tex = textures.get(id);
    if (tex) horizons.add(horizon(tex, a0, a1, shore, squash));
  }
  sky.add(horizons);
  clouds = new THREE.Group();
  for (const [id, az, el, w] of CLOUDS) {
    const tex = textures.get(id);
    if (!tex) continue;
    const img = tex.image as { width: number; height: number };
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, (w * img.height) / img.width), material(tex));
    const e = THREE.MathUtils.degToRad(el);
    mesh.position.copy(dir(az).multiplyScalar(880 * Math.cos(e))).setY(880 * Math.sin(e));
    mesh.lookAt(0, 0, 0);
    mesh.renderOrder = -1; // behind the horizons
    mesh.frustumCulled = false;
    clouds.add(mesh);
  }
  sky.add(clouds);
}

// The clouds drift slowly across the sky; the shorelines stay on the water as the camera climbs.
export function updateSky(t: number, eyeY: number) {
  clouds?.rotation.set(0, t * 0.004, 0);
  horizons?.position.setY(WATER - eyeY);
}
