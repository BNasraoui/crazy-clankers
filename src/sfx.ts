import { audioOut } from './audio';

// Layered sound on top of audio.ts: recorded crunches, thuds and splashes
// (CC0, see public/sounds/CREDITS.md), a synthesised tyre squeal that follows
// slip, and a faint electric-motor whine. Files load lazily once audio is
// unlocked by a user gesture; anything missing just stays silent.

const BANKS = {
  metal: ['crash-metal-0', 'crash-metal-1', 'crash-metal-2', 'crash-metal-3', 'crash-metal-4'],
  panel: ['crash-panel-0', 'crash-panel-2', 'crash-panel-4'],
  glass: ['crash-glass-0', 'crash-glass-2', 'crash-glass-4'],
  thud: ['thud-0', 'thud-2', 'thud-4'],
  splash: ['splash-01', 'splash-04', 'splash-07'],
  bubbles: ['bubbles'],
};
type Bank = keyof typeof BANKS;
const bank: Partial<Record<Bank, AudioBuffer[]>> = {};
let started = false;

export async function loadSound(ctx: BaseAudioContext, url: string): Promise<AudioBuffer | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await ctx.decodeAudioData(await res.arrayBuffer());
  } catch {
    return null;
  }
}

// The audio context once unlocked, starting the sample downloads the first time.
function out() {
  const o = audioOut();
  if (o && !started) {
    started = true;
    for (const [name, files] of Object.entries(BANKS) as [Bank, string[]][])
      for (const f of files) void loadSound(o.ctx, `/sounds/${f}.mp3`).then((b) => b && (bank[name] ??= []).push(b));
  }
  return o;
}

const rnd = (a: number, b: number) => a + Math.random() * (b - a);

function play(name: Bank, vol: number, rate = 1, when = 0) {
  const o = out();
  const list = bank[name];
  if (!o || !list?.length || vol <= 0.001) return;
  const src = o.ctx.createBufferSource();
  src.buffer = list[Math.floor(Math.random() * list.length)];
  src.playbackRate.value = rate;
  const g = o.ctx.createGain();
  g.gain.value = vol;
  src.connect(g).connect(o.master);
  src.start(o.ctx.currentTime + when);
}

// A real collision, on top of the synth crash: crunch, then metal, then glass for the big ones.
export function crunch(impact: number) {
  const k = Math.min(1, (impact - 5) / 20);
  play('metal', 0.35 + k * 0.45, rnd(0.62, 0.8)); // pitched down: these are car-sized
  play('panel', 0.25 + k * 0.4, rnd(0.55, 0.75), 0.015);
  if (impact > 10) play('thud', 0.6, rnd(0.6, 0.75));
  if (impact > 14) {
    play('glass', 0.25 + k * 0.35, rnd(0.85, 1.1), rnd(0.04, 0.09));
    play('metal', 0.25 * k + 0.1, rnd(0.9, 1.1), rnd(0.12, 0.2)); // debris settling
  }
  if (impact > 24) play('glass', 0.3, rnd(1.1, 1.3), rnd(0.18, 0.3));
}

// Small knocks (kerbs, scraping a wall) that don't count as crashes. Rate-limited.
let lastBump = 0;
export function bump(impact: number) {
  const o = out();
  if (!o || o.ctx.currentTime - lastBump < 0.35) return;
  lastBump = o.ctx.currentTime;
  play('thud', Math.min(0.55, 0.12 + impact * 0.08), rnd(0.75, 0.95));
}

export function splash() {
  play('splash', 0.7, rnd(0.65, 0.75)); // a whole car, not a pebble
  play('splash', 0.45, rnd(0.9, 1.0), 0.06);
  play('bubbles', 0.35, 0.8, 0.45);
}

// ---------- tyres and motor ----------

interface Loops {
  squeal: GainNode;
  squealSrc: AudioBufferSourceNode[];
  tone: BiquadFilterNode;
  scrub: GainNode;
  scrubFilter: BiquadFilterNode;
  whine: GainNode;
  whineOsc: OscillatorNode[];
}
let loops: Loops | null = null;

// Rubber stick-slip: a few detuned, wandering, harmonic-rich squeals (one per
// tyre, so they beat against each other) with ragged amplitude, over a little
// hiss. Built once at a low sample rate; it loops seamlessly.
function squealBuffer(ctx: BaseAudioContext) {
  const sr = 22050, len = sr * 3, fade = Math.floor(sr * 0.25);
  const total = len + fade;
  const data = new Float32Array(total);
  for (const [f0, amp] of [[820, 1], [965, 0.8], [1180, 0.55], [1430, 0.3]] as const) {
    let ph = Math.random() * 6, drift = 0, env = 0.6, envTarget = 0.6;
    for (let i = 0; i < total; i++) {
      if (i % 220 === 0) envTarget = 0.25 + Math.random() * 0.75; // ~100 Hz of chatter
      env += (envTarget - env) * 0.004;
      drift += (Math.random() - 0.5) * 0.004 - drift * 0.0015; // slow pitch wander
      const f = f0 * (1 + drift * 3 + 0.012 * Math.sin(i * 0.0021 + f0));
      ph += (2 * Math.PI * f) / sr;
      data[i] += amp * env * (Math.sin(ph) + 0.5 * Math.sin(2 * ph) + 0.28 * Math.sin(3 * ph + 1) + 0.12 * Math.sin(5 * ph));
    }
  }
  let prev = 0;
  for (let i = 0; i < total; i++) {
    const w = Math.random() * 2 - 1;
    data[i] += (w - prev) * 0.35; // high-passed hiss
    prev = w;
  }
  for (let i = 0; i < fade; i++) data[i] = data[i] * (i / fade) + data[len + i] * (1 - i / fade);
  let peak = 0;
  for (let i = 0; i < len; i++) peak = Math.max(peak, Math.abs(data[i]));
  const buf = ctx.createBuffer(1, len, sr);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < len; i++) ch[i] = data[i] / peak;
  return buf;
}

function noiseBuffer(ctx: BaseAudioContext) {
  const sr = 22050, buf = ctx.createBuffer(1, sr * 2, sr);
  const d = buf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return buf;
}

function buildLoops(ctx: AudioContext, master: AudioNode): Loops {
  const squeal = ctx.createGain();
  squeal.gain.value = 0;
  const tone = ctx.createBiquadFilter();
  tone.type = 'bandpass';
  tone.frequency.value = 1500;
  tone.Q.value = 0.7;
  tone.connect(squeal).connect(master);
  const buf = squealBuffer(ctx);
  // Two copies, offset and detuned, so the loop never sounds like a loop.
  const squealSrc = [0, 1].map((k) => {
    const s = ctx.createBufferSource();
    s.buffer = buf;
    s.loop = true;
    const g = ctx.createGain();
    g.gain.value = k ? 0.6 : 1;
    s.connect(g).connect(tone);
    s.start(0, k * 1.37);
    return s;
  });

  // The scrub/roar of rubber under a burnout or a skid.
  const scrub = ctx.createGain();
  scrub.gain.value = 0;
  const scrubFilter = ctx.createBiquadFilter();
  scrubFilter.type = 'bandpass';
  scrubFilter.frequency.value = 700;
  scrubFilter.Q.value = 1.2;
  const n = ctx.createBufferSource();
  n.buffer = noiseBuffer(ctx);
  n.loop = true;
  n.connect(scrubFilter).connect(scrub).connect(master);
  n.start();

  // Inverter whine: a thin, high, rising tone under the existing motor, Formula E style.
  const whine = ctx.createGain();
  whine.gain.value = 0;
  whine.connect(master);
  const whineOsc = [1, 1.5].map((mul) => {
    const o = ctx.createOscillator();
    o.type = mul === 1 ? 'sine' : 'triangle';
    o.frequency.value = 300 * mul;
    const g = ctx.createGain();
    g.gain.value = mul === 1 ? 1 : 0.25;
    o.connect(g).connect(whine);
    o.start();
    return o;
  });
  return { squeal, squealSrc, tone, scrub, scrubFilter, whine, whineOsc };
}

// slip 0..1 (how hard the tyres are sliding), spin 0..1 (wheelspin/burnout share of it).
export function setTyres(slip: number, spin: number, speed: number, throttle: number, on: boolean) {
  const o = out();
  if (!o) return;
  loops ??= buildLoops(o.ctx, o.master);
  const t = o.ctx.currentTime;
  const s = on ? slip : 0;
  const level = s * s * (3 - 2 * s); // smoothstep: quiet onset, full squeal when properly sideways
  loops.squeal.gain.setTargetAtTime(level * 0.2, t, 0.05);
  // Slip pushes the pitch up; a burnout sits lower and rougher.
  const rate = 0.82 + s * 0.3 + Math.min(speed, 40) * 0.003 - spin * 0.12;
  for (const [k, src] of loops.squealSrc.entries()) src.playbackRate.setTargetAtTime(rate * (k ? 1.06 : 1), t, 0.06);
  loops.tone.frequency.setTargetAtTime(1100 + s * 1200, t, 0.08);
  loops.scrub.gain.setTargetAtTime(on ? (level * 0.06 + spin * 0.1) : 0, t, 0.06);
  loops.scrubFilter.frequency.setTargetAtTime(450 + spin * 500 + s * 300, t, 0.1);
  const v = Math.abs(speed);
  const f = 260 + v * 52;
  loops.whineOsc[0].frequency.setTargetAtTime(f, t, 0.05);
  loops.whineOsc[1].frequency.setTargetAtTime(f * 1.5, t, 0.05);
  loops.whine.gain.setTargetAtTime(on && v > 0.5 ? 0.006 + 0.01 * throttle * Math.min(1, v / 10) : 0, t, 0.12);
}
