import * as THREE from 'three';
import { CHARACTER_LAYER, setOutlineResolution } from './anime';

// The game's look: cel lighting with one shadow tone, ink outlines drawn from
// the depth buffer, the 3D rendered at low resolution and scaled up with hard
// pixels, then film grain and speed lines on top. The HUD is DOM, so it stays sharp.

const gradientMap = (() => {
  const tex = new THREE.DataTexture(new Uint8Array([150, 255]), 2, 1, THREE.RedFormat);
  tex.minFilter = tex.magFilter = THREE.NearestFilter;
  tex.needsUpdate = true;
  return tex;
})();

export function toon(p: THREE.ColorRepresentation | THREE.MeshToonMaterialParameters = {}) {
  const params = typeof p === 'object' && !(p instanceof THREE.Color) ? p : { color: p };
  return new THREE.MeshToonMaterial({ gradientMap, ...params });
}

export const glslColor = (hex: THREE.ColorRepresentation) => {
  const c = new THREE.Color(hex);
  return `vec3(${c.r.toFixed(4)}, ${c.g.toFixed(4)}, ${c.b.toFixed(4)})`;
};

export const SKY = { zenith: 0x2c74d6, horizon: 0xd3e6f3 };

export function makeSky() {
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    vertexShader: /* glsl */ `
      varying vec3 vDir;
      void main() {
        vDir = normalize(position);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      varying vec3 vDir;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float noise(vec2 p) {
        vec2 i = floor(p), f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
      }
      float fbm(vec2 p) { return 0.55 * noise(p) + 0.3 * noise(p * 2.1) + 0.15 * noise(p * 4.3); }
      void main() {
        float h = vDir.y;
        vec3 col = mix(${glslColor(SKY.horizon)}, ${glslColor(SKY.zenith)}, smoothstep(-0.02, 0.5, h));
        // Flat cel clouds: a lit top and one shadow tone underneath.
        vec2 q = vDir.xz / max(h, 0.06) * 0.9;
        float n = fbm(q * 0.7);
        float band = smoothstep(0.03, 0.12, h) * (1.0 - smoothstep(0.55, 0.8, h));
        if (n > 0.6 && band > 0.5) col = n > 0.64 ? vec3(1.0) : ${glslColor(0xc9d6e6)};
        gl_FragColor = vec4(col, 1.0);
        #include <colorspace_fragment>
      }`,
  });
  const sky = new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), mat);
  sky.frustumCulled = false;
  sky.renderOrder = -1;
  return sky;
}

export interface LookSettings { height: number; grain: number; outline: boolean; speedLines: boolean; people: number; camBack: number; camUp: number; fov: number; paxSprites: boolean }
const DEFAULTS: LookSettings = { height: 480, grain: 0, outline: true, speedLines: true, people: 1.2, camBack: 6.5, camUp: 3, fov: 60, paxSprites: true };
const STORE = 'clankers.look.v4'; // bump when defaults change, so old saved tweaks don't hide them

function loadSettings(): LookSettings {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(STORE) ?? '{}') };
  } catch {
    return { ...DEFAULTS };
  }
}

export class Look {
  settings = loadSettings();
  private target: THREE.WebGLRenderTarget;
  private chars: THREE.WebGLRenderTarget;
  private clear = new THREE.Color();
  private quad: THREE.Mesh<THREE.PlaneGeometry, THREE.ShaderMaterial>;
  private quadScene = new THREE.Scene();
  private quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private w = 1;
  private h = 1;

  constructor(private renderer: THREE.WebGLRenderer) {
    this.target = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, depthBuffer: true });
    this.target.texture.minFilter = this.target.texture.magFilter = THREE.NearestFilter;
    this.target.depthTexture = new THREE.DepthTexture(1, 1);
    this.chars = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, depthBuffer: true });
    this.chars.texture.minFilter = this.chars.texture.magFilter = THREE.NearestFilter;
    this.chars.depthTexture = new THREE.DepthTexture(1, 1);
    // Shadows are drawn once per frame, not once per pass.
    renderer.shadowMap.autoUpdate = false;

    this.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
      uniforms: {
        tColor: { value: this.target.texture },
        tDepth: { value: this.target.depthTexture },
        tChar: { value: this.chars.texture },
        tCharDepth: { value: this.chars.depthTexture },
        uFull: { value: new THREE.Vector2(1, 1) },
        uLow: { value: new THREE.Vector2(1, 1) },
        uNear: { value: 0.5 },
        uFar: { value: 1000 },
        uTime: { value: 0 },
        uGrain: { value: 0.07 },
        uOutline: { value: 1 },
        uSpeed: { value: 0 },
        uAspect: { value: 1 },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
      fragmentShader: /* glsl */ `
        #include <packing>
        uniform sampler2D tColor;
        uniform sampler2D tDepth;
        uniform sampler2D tChar;
        uniform sampler2D tCharDepth;
        uniform vec2 uLow;
        uniform vec2 uFull;
        uniform float uNear, uFar, uTime, uGrain, uOutline, uSpeed, uAspect;
        varying vec2 vUv;

        // 1/distance is linear across a flat surface in screen space, so its
        // Laplacian is zero on planes and spikes at creases and silhouettes.
        float invZ(vec2 uv) {
          float d = texture2D(tDepth, uv).x;
          return 1.0 / max(-perspectiveDepthToViewZ(d, uNear, uFar), 0.001);
        }
        float charInvZ(vec2 uv) {
          float d = texture2D(tCharDepth, uv).x;
          return 1.0 / max(-perspectiveDepthToViewZ(d, uNear, uFar), 0.001);
        }
        float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

        void main() {
          vec2 uv = (floor(vUv * uLow) + 0.5) / uLow;
          vec3 col = texture2D(tColor, uv).rgb;

          if (uOutline > 0.5) {
            vec2 t = 1.0 / uLow;
            float c = invZ(uv);
            float l = invZ(uv - vec2(t.x, 0.0));
            float r = invZ(uv + vec2(t.x, 0.0));
            float u = invZ(uv + vec2(0.0, t.y));
            float d = invZ(uv - vec2(0.0, t.y));
            float lap = abs(4.0 * c - l - r - u - d) / c;
            // Only ink the nearer side of a silhouette, so lines stay one pixel wide.
            float nearer = step(max(max(l, r), max(u, d)) * 0.5, c);
            float edge = smoothstep(0.06, 0.16, lap) * nearer;
            edge *= smoothstep(1.0 / 420.0, 1.0 / 260.0, c);
            col = mix(col, ${glslColor(0x1b1722)}, edge * 0.92);
          }

          // Characters, at full resolution, wherever they're in front of the world.
          float isChar = 0.0;
          vec4 ch = texture2D(tChar, vUv);
          if (ch.a > 0.5) {
            float charDist = -perspectiveDepthToViewZ(texture2D(tCharDepth, vUv).x, uNear, uFar);
            if (charDist < 1.0 / invZ(uv) + 0.4) {
              col = ch.rgb;
              isChar = 1.0;
              // Ink on creases inside the silhouette (car panel breaks, bumpers, arches),
              // found the same way as the world's lines: where 1/depth stops being planar.
              vec2 t = 1.0 / uFull;
              float c = charInvZ(vUv);
              float lap = abs(4.0 * c - charInvZ(vUv - vec2(t.x, 0.0)) - charInvZ(vUv + vec2(t.x, 0.0))
                                   - charInvZ(vUv - vec2(0.0, t.y)) - charInvZ(vUv + vec2(0.0, t.y))) / c;
              float crease = smoothstep(0.012, 0.03, lap) * smoothstep(1.0 / 60.0, 1.0 / 25.0, c);
              col = mix(col, ${glslColor(0x1b1722)}, crease * 0.85);
            }
          }

          // Manga speed lines from the screen edges.
          if (uSpeed > 0.0) {
            vec2 p = vUv - 0.5;
            p.x *= uAspect;
            float a = (atan(p.y, p.x) + 3.14159) / 6.28318 * 180.0;
            float on = step(0.82, hash(vec2(floor(a), floor(uTime * 16.0))));
            float thin = 1.0 - smoothstep(0.08, 0.2, abs(fract(a) - 0.5));
            float sl = on * thin * smoothstep(0.34, 0.7, length(p)) * uSpeed;
            col = mix(col, vec3(1.0), sl * 0.6);
          }

          // Film grain on the world only, re-rolled 12 times a second (film, not TV static).
          float frame = floor(uTime * 12.0);
          col += (hash(floor(gl_FragCoord.xy / 2.0) + fract(frame * 0.6180339) * 517.0) - 0.5) * uGrain * (1.0 - isChar);
          col *= 1.0 - 0.2 * smoothstep(0.5, 0.95, length((vUv - 0.5) * vec2(uAspect, 1.0)));
          gl_FragColor = vec4(col, 1.0);
          #include <colorspace_fragment>
        }`,
      depthTest: false,
      depthWrite: false,
    }));
    this.quad.frustumCulled = false;
    this.quadScene.add(this.quad);
    this.buildPanel();
  }

  setSize(w: number, h: number) {
    this.w = w;
    this.h = h;
    const lh = Math.min(h, this.settings.height);
    const lw = Math.round((lh * w) / h);
    this.target.setSize(lw, lh);
    const pr = this.renderer.getPixelRatio();
    this.chars.setSize(Math.round(w * pr), Math.round(h * pr));
    this.quad.material.uniforms.uFull.value.set(Math.round(w * pr), Math.round(h * pr));
    setOutlineResolution(Math.round(w * pr), Math.round(h * pr));
    this.quad.material.uniforms.uLow.value.set(lw, lh);
    this.quad.material.uniforms.uAspect.value = w / h;
  }

  render(scene: THREE.Scene, camera: THREE.PerspectiveCamera, time: number, speed: number) {
    const u = this.quad.material.uniforms;
    u.uNear.value = camera.near;
    u.uFar.value = camera.far;
    u.uTime.value = time;
    u.uGrain.value = this.settings.grain;
    u.uOutline.value = this.settings.outline ? 1 : 0;
    u.uSpeed.value = this.settings.speedLines ? speed : 0;
    const r = this.renderer;
    r.shadowMap.needsUpdate = true;
    camera.layers.set(0);
    r.setRenderTarget(this.target);
    r.render(scene, camera);

    // Characters on their own transparent layer.
    const background = scene.background;
    const alpha = r.getClearAlpha();
    r.getClearColor(this.clear);
    scene.background = null;
    r.setClearColor(0x000000, 0);
    camera.layers.set(CHARACTER_LAYER);
    r.setRenderTarget(this.chars);
    r.render(scene, camera);
    camera.layers.set(0);
    scene.background = background;
    r.setClearColor(this.clear, alpha);
    r.setRenderTarget(null);
    this.renderer.render(this.quadScene, this.quadCam);
  }

  // Backquote (`) or the controller's Select button toggles a tuning panel.
  private buildPanel() {
    const panel = document.createElement('div');
    panel.id = 'lookpanel';
    panel.hidden = true;
    panel.innerHTML = `
      <b>LOOK</b>
      <label>Resolution <select id="lk-res">
        ${[240, 360, 480, 720, 4000].map((v) => `<option value="${v}">${v === 4000 ? 'native' : v + 'p'}</option>`).join('')}
      </select></label>
      <label>Grain <input id="lk-grain" type="range" min="0" max="0.25" step="0.01"></label>
      <label><input id="lk-outline" type="checkbox"> Outlines</label>
      <label><input id="lk-speed" type="checkbox"> Speed lines</label>
      <label>People size <input id="lk-people" type="range" min="0.8" max="2" step="0.05"><output id="lk-people-v"></output></label>
      <label>Camera distance <input id="lk-back" type="range" min="4" max="12" step="0.25"><output id="lk-back-v"></output></label>
      <label>Camera height <input id="lk-up" type="range" min="1.5" max="7" step="0.1"><output id="lk-up-v"></output></label>
      <label>Field of view <input id="lk-fov" type="range" min="45" max="90" step="1"><output id="lk-fov-v"></output></label>
      <label><input id="lk-pax" type="checkbox"> Passengers as sprites</label>
      <button id="lk-reset" type="button">Reset</button>
      <b>CONTROLLERS</b>
      <pre id="lk-pads"></pre>`;
    document.body.appendChild(panel);
    const res = panel.querySelector<HTMLSelectElement>('#lk-res')!;
    const grain = panel.querySelector<HTMLInputElement>('#lk-grain')!;
    const outline = panel.querySelector<HTMLInputElement>('#lk-outline')!;
    const speed = panel.querySelector<HTMLInputElement>('#lk-speed')!;
    const people = panel.querySelector<HTMLInputElement>('#lk-people')!;
    const peopleV = panel.querySelector<HTMLOutputElement>('#lk-people-v')!;
    const slider = (id: string) => [panel.querySelector<HTMLInputElement>(`#lk-${id}`)!, panel.querySelector<HTMLOutputElement>(`#lk-${id}-v`)!] as const;
    const [back, backV] = slider('back'), [up, upV] = slider('up'), [fov, fovV] = slider('fov');
    const pax = panel.querySelector<HTMLInputElement>('#lk-pax')!;
    const show = () => {
      peopleV.value = `${this.settings.people.toFixed(2)}×`;
      backV.value = `${this.settings.camBack.toFixed(1)} m`;
      upV.value = `${this.settings.camUp.toFixed(1)} m`;
      fovV.value = `${this.settings.fov}°`;
    };
    const fill = () => {
      res.value = String(this.settings.height);
      grain.value = String(this.settings.grain);
      outline.checked = this.settings.outline;
      speed.checked = this.settings.speedLines;
      people.value = String(this.settings.people);
      back.value = String(this.settings.camBack);
      up.value = String(this.settings.camUp);
      fov.value = String(this.settings.fov);
      pax.checked = this.settings.paxSprites;
      show();
    };
    res.value = String(this.settings.height);
    grain.value = String(this.settings.grain);
    outline.checked = this.settings.outline;
    speed.checked = this.settings.speedLines;
    fill();
    const apply = () => {
      this.settings = {
        height: +res.value, grain: +grain.value, outline: outline.checked, speedLines: speed.checked,
        people: +people.value, camBack: +back.value, camUp: +up.value, fov: +fov.value, paxSprites: pax.checked,
      };
      show();
      this.onChange();
      try { localStorage.setItem(STORE, JSON.stringify(this.settings)); } catch { /* storage unavailable */ }
      this.setSize(this.w, this.h);
    };
    for (const el of [res, grain, outline, speed, people, back, up, fov, pax]) el.addEventListener('input', apply);
    panel.querySelector('#lk-reset')!.addEventListener('click', () => {
      this.settings = { ...DEFAULTS };
      try { localStorage.removeItem(STORE); } catch { /* storage unavailable */ }
      fill();
      this.setSize(this.w, this.h);
      this.onChange();
    });
    addEventListener('keydown', (e) => { if (e.code === 'Backquote') panel.hidden = !panel.hidden; });
    this.togglePanel = () => { panel.hidden = !panel.hidden; };
  }

  togglePanel = () => {};
  setPadDebug(text: string) {
    const el = document.getElementById('lk-pads');
    if (el && !el.closest('[hidden]') && el.textContent !== text) el.textContent = text;
  }
  onChange = () => {};
}
