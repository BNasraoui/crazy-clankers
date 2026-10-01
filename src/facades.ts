import * as THREE from 'three';
import { toon } from './look';
import { pool, retry } from './scenery';

// Painted facades: generated drawings of SF buildings (public/facades/), set on the
// street faces of houses. One merged mesh per drawing keeps draw calls low.

export interface FacadeImage { id: string; kind: 'house' | 'tile' | 'towerbase' | 'drop'; wall: string; base: string }
export let facadeSets: Record<string, FacadeImage[]> = {};
const textures = new Map<string, THREE.Texture>();

// Loads the manifest and every drawing up front, so no wall waits on (or loses) its texture.
export async function loadFacades() {
  try {
    facadeSets = await retry(async () => (await fetch('/facades/manifest.json')).json());
  } catch (err) {
    console.warn('No facade manifest:', err);
    return;
  }
  const loader = new THREE.TextureLoader();
  const repeats = new Set(Object.values(facadeSets).flat().filter((f) => f.kind !== 'house').map((f) => f.id));
  const ids = [...new Set(Object.values(facadeSets).flat().map((f) => f.id))];
  await pool(ids, 4, async (id) => {
    try {
      const tex = await retry(() => loader.loadAsync(`/facades/${id}.jpg`));
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 8;
      if (repeats.has(id)) tex.wrapS = tex.wrapT = THREE.RepeatWrapping; // tiles and lobbies repeat
      textures.set(id, tex);
    } catch (err) {
      console.warn(`No facade ${id}:`, err);
    }
  });
  // Drop drawings that never arrived; their lots fall back to plain houses.
  for (const d of Object.keys(facadeSets)) facadeSets[d] = facadeSets[d].filter((f) => textures.has(f.id));
}

export const houseSet = (district: string) => (facadeSets[district] ?? []).filter((f) => f.kind === 'house');

// A painted rectangle on a wall: centred at (cx, cz), facing (nx, nz), spanning y0..y1.
// For tiles, repeatV says how many times the drawing repeats up the wall.
export interface Card { image: string; cx: number; cz: number; nx: number; nz: number; width: number; y0: number; y1: number; repeatU?: number; repeatV?: number; lift?: number }

export class FacadeBuilder {
  private quads = new Map<string, number[]>(); // image (or "#colour") -> interleaved pos(3) uv(2)

  add(c: Card) {
    const key = c.image;
    const arr = this.quads.get(key) ?? [];
    this.quads.set(key, arr);
    // Right-hand vector along the wall, looking at its face.
    const rx = c.nz, rz = -c.nx;
    const lift = c.lift ?? 0.03;
    const x = c.cx + c.nx * lift, z = c.cz + c.nz * lift;
    const hw = c.width / 2;
    const u = c.repeatU ?? 1, v = c.repeatV ?? 1;
    const p = [
      [x - rx * hw, c.y0, z - rz * hw, 0, 0], [x + rx * hw, c.y0, z + rz * hw, u, 0],
      [x + rx * hw, c.y1, z + rz * hw, u, v], [x - rx * hw, c.y1, z - rz * hw, 0, v],
    ];
    for (const i of [0, 1, 2, 0, 2, 3]) arr.push(...p[i]);
  }

  // A flat-coloured band (foundations on slopes, plain walls).
  addColour(colour: string, c: Omit<Card, 'image'>) {
    this.add({ ...c, image: `#${colour.replace('#', '')}` });
  }

  build(): THREE.Group {
    const g = new THREE.Group();
    for (const [key, data] of this.quads) {
      const geo = new THREE.BufferGeometry();
      const n = data.length / 5;
      const pos = new Float32Array(n * 3), uv = new Float32Array(n * 2);
      for (let i = 0; i < n; i++) {
        pos.set(data.slice(i * 5, i * 5 + 3), i * 3);
        uv.set(data.slice(i * 5 + 3, i * 5 + 5), i * 2);
      }
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
      geo.computeVertexNormals();
      let mat: THREE.Material;
      if (key.startsWith('#')) mat = toon({ color: new THREE.Color(key) });
      else mat = toon({ map: textures.get(key) });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.receiveShadow = true;
      g.add(mesh);
    }
    return g;
  }
}
