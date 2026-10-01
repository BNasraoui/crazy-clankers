import * as THREE from 'three';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

// Characters (passengers and the player's cab) are drawn like anime cels:
// one hard light/shadow split with a tinted shadow colour, an ink outline of
// constant on-screen width, and their own full-resolution layer so they stay
// crisp over the low-resolution world.

export const CHARACTER_LAYER = 1;
export const INK = new THREE.Color(0x1b1722);

// World-space direction towards the sun; the game keeps it in sync.
export const sunDir = { value: new THREE.Vector3(0.5, 0.8, 0.3).normalize() };
const outlineRes = { value: new THREE.Vector2(1280, 720) };
export const setOutlineResolution = (w: number, h: number) => outlineRes.value.set(w, h);

// Shadow tint per material role: warm for skin, cool for everything else.
function shadeFor(name: string) {
  return /skin|face/.test(name) ? new THREE.Color(0.86, 0.66, 0.64) : new THREE.Color(0.7, 0.72, 0.86);
}

export function animeMaterial(src: THREE.MeshStandardMaterial | THREE.MeshToonMaterial) {
  const map = src.map ?? null;
  return new THREE.ShaderMaterial({
    defines: map ? { USE_MAP: '' } : {},
    transparent: src.transparent,
    uniforms: {
      uColor: { value: src.color.clone() },
      uShade: { value: shadeFor(src.name) },
      uMap: { value: map },
      uSun: sunDir,
      uAlphaTest: { value: src.alphaTest || (src.transparent ? 0.5 : 0) },
    },
    vertexShader: /* glsl */ `
      varying vec3 vNormal;
      varying vec2 vUv;
      void main() {
        vNormal = normalize(mat3(modelMatrix) * normal);
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor;
      uniform vec3 uShade;
      uniform vec3 uSun;
      uniform float uAlphaTest;
      #ifdef USE_MAP
      uniform sampler2D uMap;
      #endif
      varying vec3 vNormal;
      varying vec2 vUv;
      void main() {
        vec4 base = vec4(uColor, 1.0);
        #ifdef USE_MAP
        base *= texture2D(uMap, vUv);
        #endif
        if (base.a < uAlphaTest) discard;
        float lit = smoothstep(-0.04, 0.04, dot(normalize(vNormal), uSun));
        gl_FragColor = vec4(mix(base.rgb * uShade, base.rgb, lit), 1.0);
        #include <colorspace_fragment>
      }`,
  });
}

const outlineMaterial = new THREE.ShaderMaterial({
  side: THREE.BackSide,
  uniforms: { uRes: outlineRes, uWidth: { value: 2.2 }, uInk: { value: INK } },
  vertexShader: /* glsl */ `
    uniform vec2 uRes;
    uniform float uWidth;
    void main() {
      vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      vec2 n = (projectionMatrix * vec4(normalize(normalMatrix * normal), 0.0)).xy;
      clip.xy += normalize(n + 1e-6) * uWidth * clip.w * 2.0 / uRes;
      gl_Position = clip;
    }`,
  fragmentShader: /* glsl */ `
    uniform vec3 uInk;
    void main() {
      gl_FragColor = vec4(uInk, 1.0);
      #include <colorspace_fragment>
    }`,
});

// Hull normals are smoothed across hard edges so the outline never cracks.
function hullGeometry(geo: THREE.BufferGeometry) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', geo.getAttribute('position'));
  if (geo.index) g.setIndex(geo.index);
  const merged = mergeVertices(g, 1e-4);
  merged.computeVertexNormals();
  return merged;
}

// Turn an imported model into an anime character: cel materials, ink outlines,
// and the character render layer. Shares outline geometry between clones.
export function makeCharacter(root: THREE.Object3D) {
  const meshes: THREE.Mesh[] = [];
  root.traverse((o) => { if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh); });
  for (const mesh of meshes) {
    const src = mesh.material as THREE.MeshStandardMaterial;
    if (!('color' in src)) continue;
    mesh.material = src.name.startsWith('light_') ? new THREE.MeshBasicMaterial({ color: src.color }) : animeMaterial(src);
    mesh.castShadow = true;
    const hull = new THREE.Mesh(hullGeometry(mesh.geometry), outlineMaterial);
    hull.name = `${mesh.name}_outline`;
    mesh.add(hull);
  }
  setLayer(root);
  return root;
}

export function setLayer(root: THREE.Object3D, layer = CHARACTER_LAYER) {
  root.traverse((o) => o.layers.set(layer));
}
