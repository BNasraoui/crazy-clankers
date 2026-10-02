import * as THREE from 'three';
import { audioOut } from './audio';
import { loadSound } from './sfx';
import { CHARACTER_LAYER } from './anime';
import type { Pedestrians, Shout } from './pedestrians';

// Pedestrians yelling at the cab: recorded voice clips (Kokoro TTS, see
// tools/voices/) panned to where the person is, with a manga speech bubble over
// their head. Strictly rationed so a busy sidewalk never turns into a wall of noise.

interface Clip { file: string; kinds: string[]; text: string; scream: boolean; dur: number; buf?: AudioBuffer }
interface Voice { pos: THREE.Vector3; pan: StereoPannerNode; gain: GainNode; level: number; end: number }
interface Bubble { sprite: THREE.Sprite; pos: THREE.Vector3 | null; t: number; life: number; w: number; h: number }

const MAX_VOICES = 2;
const GAP = 0.4; // seconds between any two voices starting
const LINE_GAP = 2.4; // ...and between two full sentences
const HEARING = 50; // metres; further away than this, nobody hears you
const INK = '#1b1722';

export class Voices {
  private clips: Clip[] = [];
  private bags = new Map<string, Clip[]>();
  private loading = false;
  private voices: Voice[] = [];
  private lastStart = -9;
  private lastLine = -9;
  private bubbles: Bubble[] = [];
  private textures = new Map<string, { tex: THREE.CanvasTexture; aspect: number; h: number }>();
  private right = new THREE.Vector3();
  private to = new THREE.Vector3();

  constructor(scene: THREE.Scene) {
    for (let k = 0; k < 3; k++) {
      // On the character layer, which the look only shows where its depth is in front of the world,
      // so it has to write depth (and WebGL skips depth writes when depth testing is off).
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ alphaTest: 0.5 }));
      sprite.layers.set(CHARACTER_LAYER);
      sprite.renderOrder = 11;
      sprite.visible = false;
      scene.add(sprite);
      this.bubbles.push({ sprite, pos: null, t: 0, life: 0, w: 1, h: 1 });
    }
  }

  private async load(ctx: AudioContext) {
    this.loading = true;
    try {
      const res = await fetch('/sounds/voices/voices.json');
      if (!res.ok) return;
      this.clips = (await res.json()).clips;
    } catch {
      return;
    }
    // One at a time, so decoding never competes with the game for long.
    for (const c of this.clips) c.buf = (await loadSound(ctx, `/sounds/voices/${c.file}`)) ?? undefined;
  }

  update(dt: number, camera: THREE.Camera, peds: Pedestrians | null) {
    const o = audioOut();
    if (o && !this.loading) void this.load(o.ctx);
    this.right.setFromMatrixColumn(camera.matrixWorld, 0);
    if (o) {
      const now = o.ctx.currentTime;
      this.voices = this.voices.filter((v) => now < v.end);
      for (const v of this.voices) this.place(v, camera, now);
    }
    const size = peds?.size ?? 1.3;
    for (const b of this.bubbles) this.drawBubble(b, dt, size, camera);
    if (o && peds) for (const s of peds.shouts) this.react(s, camera, o.ctx, o.master);
  }

  private react(s: Shout, camera: THREE.Camera, ctx: AudioContext, master: GainNode) {
    const now = ctx.currentTime;
    if (this.voices.length >= MAX_VOICES || now - this.lastStart < GAP) return;
    if (s.pos.distanceTo(camera.position) > HEARING) return;
    let scream = s.scream;
    if (!scream && now - this.lastLine < LINE_GAP) {
      if (Math.random() < 0.5) return;
      scream = true; // too soon for another sentence; just a yelp
    }
    const clip = this.pick(s.kind, scream);
    if (!clip?.buf) return;
    this.lastStart = now;
    if (!scream) this.lastLine = now;

    const src = ctx.createBufferSource();
    src.buffer = clip.buf;
    const rate = 0.95 + Math.random() * 0.1;
    src.playbackRate.value = rate;
    const gain = ctx.createGain();
    const pan = ctx.createStereoPanner();
    src.connect(gain).connect(pan).connect(master);
    const v: Voice = { pos: s.pos, pan, gain, level: scream ? 0.8 : 1, end: now + clip.dur / rate + 0.05 };
    this.place(v, camera, now, true);
    src.start();
    this.voices.push(v);
    this.say(s.pos, clip, scream);
  }

  // Pan and level from where the person is relative to the camera.
  private place(v: Voice, camera: THREE.Camera, now: number, snap = false) {
    const d = this.to.copy(v.pos).sub(camera.position).length();
    const pan = THREE.MathUtils.clamp(this.to.dot(this.right) / Math.max(d, 1), -1, 1) * 0.85;
    const level = v.level * Math.min(1, 1.6 / (1 + d / 9));
    if (snap) {
      v.pan.pan.value = pan;
      v.gain.gain.value = level;
    } else {
      v.pan.pan.setTargetAtTime(pan, now, 0.05);
      v.gain.gain.setTargetAtTime(level, now, 0.05);
    }
  }

  // Shuffle bags per kind of person, so lines don't repeat until they've all been heard.
  private pick(kind: string, scream: boolean) {
    const key = `${kind}:${scream}`;
    let bag = this.bags.get(key);
    if (!bag?.length) {
      bag = this.clips.filter((c) => c.buf && c.scream === scream && c.kinds.includes(kind));
      this.bags.set(key, bag);
    }
    if (!bag.length) return null;
    return bag.splice(Math.floor(Math.random() * bag.length), 1)[0];
  }

  // ---------- speech bubbles ----------

  private say(pos: THREE.Vector3, clip: Clip, scream: boolean) {
    const b = this.bubbles.find((b) => !b.sprite.visible) ?? this.bubbles.reduce((a, b) => (a.t / a.life > b.t / b.life ? a : b));
    const { tex, aspect, h } = this.texture(clip.text, scream);
    const mat = b.sprite.material;
    const old = mat.map;
    if (old && ![...this.textures.values()].some((t) => t.tex === old)) old.dispose();
    mat.map = tex;
    mat.needsUpdate = true;
    b.h = h;
    b.w = h * aspect;
    b.pos = pos;
    b.t = 0;
    b.life = Math.max(1.4, clip.dur + 0.7);
    b.sprite.visible = true;
  }

  private drawBubble(b: Bubble, dt: number, size: number, camera: THREE.Camera) {
    if (!b.sprite.visible || !b.pos) return;
    b.t += dt;
    if (b.t > b.life) {
      b.sprite.visible = false;
      b.pos = null;
      return;
    }
    // Pop in with a little overshoot, then sit still.
    const k = b.t < 0.12 ? (b.t / 0.12) * 1.15 : b.t < 0.2 ? 1.15 - ((b.t - 0.12) / 0.08) * 0.15 : 1;
    // Slide it a few metres towards the camera, shrunk to match, so the street
    // tree beside the speaker doesn't swallow it. It looks exactly the same.
    const at = this.to.set(b.pos.x, b.pos.y + 1.75 * size + 0.5 + b.h * 0.5, b.pos.z);
    const d = at.distanceTo(camera.position);
    const pull = Math.max(0.4, (d - 5) / d);
    b.sprite.position.copy(camera.position).lerp(at, pull);
    b.sprite.scale.set(b.w * k * pull, b.h * k * pull, 1);
  }

  private texture(text: string, scream: boolean) {
    const key = `${scream}:${text}`;
    const hit = this.textures.get(key);
    if (hit) return hit;
    const font = scream ? '64px "Dela Gothic One", Impact, sans-serif' : '46px "Permanent Marker", "Comic Sans MS", sans-serif';
    const c = document.createElement('canvas');
    const g = c.getContext('2d')!;
    g.font = font;
    const lines = wrap(g, text, scream ? 600 : 380);
    const lh = scream ? 70 : 54;
    const tw = Math.max(...lines.map((l) => g.measureText(l).width));
    const pad = scream ? 70 : 46;
    c.width = Math.ceil(tw + pad * 2);
    c.height = Math.ceil(lines.length * lh + pad * 2 + (scream ? 0 : 34));
    const cx = c.width / 2, cy = (c.height - (scream ? 0 : 34)) / 2;
    const rx = c.width / 2 - 8, ry = cy - 8;
    g.lineJoin = 'round';
    g.lineWidth = 7;
    g.strokeStyle = INK;
    g.fillStyle = scream ? '#fff27a' : '#ffffff';
    g.beginPath();
    if (scream) {
      // A spiky shout burst.
      const n = 22;
      for (let k = 0; k < n * 2; k++) {
        const a = (k / (n * 2)) * Math.PI * 2, r = k % 2 ? 0.8 : 1;
        g.lineTo(cx + Math.cos(a) * rx * r, cy + Math.sin(a) * ry * r);
      }
      g.closePath();
    } else {
      // A round balloon with a tail pointing down at the speaker.
      g.ellipse(cx, cy, rx, ry, 0, 0.62 * Math.PI, 0.38 * Math.PI + 2 * Math.PI);
      g.lineTo(cx + 6, c.height - 6);
      g.closePath();
    }
    g.fill();
    g.stroke();
    g.font = font;
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillStyle = scream ? '#d6332b' : INK;
    lines.forEach((l, i) => g.fillText(l, cx, cy + (i - (lines.length - 1) / 2) * lh + 2));
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    const out = { tex, aspect: c.width / c.height, h: c.height / 115 }; // metres tall
    // Draw again next time if the web font hadn't arrived yet.
    if (document.fonts.check(font)) this.textures.set(key, out);
    return out;
  }
}

function wrap(g: CanvasRenderingContext2D, text: string, max: number) {
  const lines: string[] = [];
  let cur = '';
  for (const w of text.split(' ')) {
    const next = cur ? `${cur} ${w}` : w;
    if (cur && g.measureText(next).width > max) {
      lines.push(cur);
      cur = w;
    } else cur = next;
  }
  lines.push(cur);
  return lines;
}
