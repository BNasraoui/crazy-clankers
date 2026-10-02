import * as THREE from 'three';
import { toon } from './look';
import { pool, retry } from './scenery';

// Painted facades: generated drawings of SF buildings (public/facades/), set on the
// street faces of houses. One merged mesh per drawing keeps draw calls low.

export interface FacadeImage { id: string; kind: 'house' | 'tile' | 'towerbase' | 'drop'; wall: string; base: string }
export let facadeSets: Record<string, FacadeImage[]> = {};
const textures = new Map<string, THREE.Texture>();
const waiting = new Map<string, ((tex: THREE.Texture) => void)[]>(); // materials waiting for a drawing
const wallOf = new Map<string, string>();

// Only the (small) manifest is awaited, so the title doesn't wait on 3 MB of drawings. Each
// building starts in its own wall colour and its drawing paints in as it arrives (see build()).
export async function loadFacades() {
  try {
    facadeSets = await retry(async () => (await fetch('/facades/manifest.json')).json());
  } catch (err) {
    console.warn('No facade manifest:', err);
    return;
  }
  for (const f of Object.values(facadeSets).flat()) wallOf.set(f.id, f.wall);
}

// The drawings themselves, started once the game is up so they don't hold up the files it needs first.
// Resolves when every drawing has arrived (or given up).
export function paintFacades(): Promise<unknown> {
  const all = Object.values(facadeSets).flat();
  const repeats = new Set(all.filter((f) => f.kind !== 'house').map((f) => f.id));
  const loader = new THREE.TextureLoader();
  return pool([...new Set(all.map((f) => f.id))], 4, async (id) => {
    try {
      const tex = await retry(() => loader.loadAsync(`/facades/${id}.avif`));
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 8;
      if (repeats.has(id)) tex.wrapS = tex.wrapT = THREE.RepeatWrapping; // tiles and lobbies repeat
      textures.set(id, tex);
      for (const done of waiting.get(id) ?? []) done(tex);
      waiting.delete(id);
    } catch (err) {
      console.warn(`No facade ${id}:`, err); // that wall keeps its plain colour
    }
  });
}

// Calls back with the drawing now if it has arrived, or as soon as it does.
function whenDrawn(id: string, done: (tex: THREE.Texture) => void) {
  const tex = textures.get(id);
  if (tex) done(tex);
  else waiting.set(id, [...(waiting.get(id) ?? []), done]);
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
      else {
        // The wall colour until the drawing arrives, then the drawing.
        const m = toon({ color: new THREE.Color(wallOf.get(key) ?? '#cfc6b4') });
        whenDrawn(key, (tex) => { m.map = tex; m.color.set(0xffffff); m.needsUpdate = true; });
        mat = m;
      }
      const mesh = new THREE.Mesh(geo, mat);
      mesh.receiveShadow = true;
      g.add(mesh);
    }
    return g;
  }
}
