// Everything is synthesized; no audio files.
let voiceUntil = 0;
export const voiceActive = () => performance.now() < voiceUntil;

let ctx: AudioContext | null = null;
let master: GainNode;
let engineGain: GainNode;
let engineOsc: OscillatorNode[] = [];
let engineFilter: BiquadFilterNode;

export function unlockAudio() {
  if (!ctx) {
    ctx = new AudioContext();
    master = ctx.createGain();
    master.gain.value = 0.45;
    master.connect(ctx.destination);

    engineFilter = ctx.createBiquadFilter();
    engineFilter.type = 'lowpass';
    engineFilter.frequency.value = 400;
    engineGain = ctx.createGain();
    engineGain.gain.value = 0;
    engineFilter.connect(engineGain).connect(master);
    // An electric whine rather than a petrol engine.
    for (const [type, mul] of [['sawtooth', 1], ['triangle', 2.01]] as const) {
      const o = ctx.createOscillator();
      o.type = type;
      o.frequency.value = 60 * mul;
      o.connect(engineFilter);
      o.start();
      engineOsc.push(o);
    }
  }
  if (ctx.state === 'suspended') void ctx.resume();
}

export function setEngine(speed: number, throttle: number, on: boolean) {
  if (!ctx) return;
  const t = ctx.currentTime;
  const f = 70 + Math.abs(speed) * 9;
  engineOsc[0].frequency.setTargetAtTime(f, t, 0.05);
  engineOsc[1].frequency.setTargetAtTime(f * 2.01, t, 0.05);
  engineFilter.frequency.setTargetAtTime(300 + throttle * 900 + Math.abs(speed) * 20, t, 0.08);
  engineGain.gain.setTargetAtTime(on ? 0.05 + throttle * 0.04 : 0, t, 0.1);
}

function tone(freq: number, dur: number, type: OscillatorType = 'square', vol = 0.12, when = 0, slideTo?: number) {
  if (!ctx) return;
  const t = ctx.currentTime + when;
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
  g.gain.setValueAtTime(vol, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + dur);
  o.connect(g).connect(master);
  o.start(t);
  o.stop(t + dur + 0.02);
}

function noise(dur: number, vol: number, cutoff: number) {
  if (!ctx) return;
  const len = Math.floor(ctx.sampleRate * dur);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len) ** 2;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  const f = ctx.createBiquadFilter();
  f.type = 'lowpass';
  f.frequency.value = cutoff;
  const g = ctx.createGain();
  g.gain.value = vol;
  src.connect(f).connect(g).connect(master);
  src.start();
}

// Animal Crossing-style babble: one blip per couple of letters.
export function babble(text: string, pitch: number) {
  const n = Math.min(14, Math.ceil(text.length / 3));
  voiceUntil = performance.now() + n * 70 + 100;
  for (let i = 0; i < n; i++) tone(pitch * (0.85 + Math.random() * 0.4), 0.05, 'square', 0.05, i * 0.07);
}

export const sfx = {
  crash: (power: number) => { noise(0.35, Math.min(0.6, 0.15 + power * 0.02), 900); tone(90, 0.25, 'sawtooth', 0.12, 0, 40); },
  honk: () => { tone(392, 0.28, 'square', 0.06); tone(330, 0.28, 'square', 0.06); },
  pickup: () => [523, 659, 784].forEach((f, i) => tone(f, 0.12, 'triangle', 0.15, i * 0.07)),
  cash: () => { [988, 1319, 1568, 2093].forEach((f, i) => tone(f, 0.1, 'square', 0.07, i * 0.06)); noise(0.15, 0.08, 6000); },
  bad: () => [392, 311, 233].forEach((f, i) => tone(f, 0.18, 'sawtooth', 0.09, i * 0.12)),
  tip: () => tone(1320, 0.08, 'square', 0.06, 0, 1760),
  whoosh: () => noise(0.4, 0.12, 2200),
  land: (power: number) => noise(0.18, Math.min(0.3, power * 0.05), 400),
  hop: () => tone(220, 0.18, 'square', 0.08, 0, 520),
  armed: () => [440, 660, 880].forEach((f, i) => tone(f, 0.09, 'square', 0.06, i * 0.05)),
  dash: () => { tone(180, 0.25, 'sawtooth', 0.08, 0, 720); noise(0.3, 0.1, 3000); },
  smash: () => { noise(0.12, 0.18, 1800); tone(140, 0.1, 'square', 0.06, 0, 70); },
  splash: () => { noise(0.7, 0.35, 1500); tone(300, 0.4, 'sine', 0.08, 0, 80); },
  geyser: () => noise(1.2, 0.2, 5000),
  timber: () => { noise(0.5, 0.3, 700); tone(160, 0.5, 'sawtooth', 0.08, 0, 50); noise(0.6, 0.12, 3500); },
  yelp: () => tone(700 + Math.random() * 400, 0.22, 'triangle', 0.07, 0, 1300 + Math.random() * 500),
};

// For src/sfx.ts and src/voices.ts: the shared context and master bus, once unlocked.
export const audioOut = () => (ctx ? { ctx, master } : null);
