// What a passenger wants from this ride, and the 1-5 stars they'll give for it.
// Every passenger picks one want per trip from their own pool (passengers.ts).

import { t } from './i18n';

export type WantId = 'speed' | 'air' | 'drift' | 'closecalls' | 'reckless' | 'smooth' | 'ontime';
const FAST = 20; // m/s, about 45 mph

export type Feed = 'jump' | 'hop' | 'nearMiss' | 'drift' | 'smash' | 'crash';

interface WantDef {
  title: string;
  how: string; // one line on what counts
  icon: string;
  thresholds: number[]; // value for 1..5 stars, before scaling by trip length
  scaled: boolean; // cumulative over the ride, so longer rides need more
  show: (v: number) => string;
}

const secs = (v: number) => t('unit.s', { n: v.toFixed(1) });
const def = (id: WantId, d: Omit<WantDef, 'title' | 'how'>): WantDef => ({
  ...d,
  get title() { return t(`want.${id}`); },
  get how() { return t(`want.${id}.how`); },
});

export const WANTS: Record<WantId, WantDef> = {
  speed: def('speed', { icon: '💨', thresholds: [2, 5, 8, 12, 16], scaled: true, show: secs }),
  air: def('air', { icon: '🛫', thresholds: [1, 2.5, 4, 6, 8], scaled: true, show: secs }),
  drift: def('drift', { icon: '🌀', thresholds: [1.5, 4, 7, 11, 16], scaled: true, show: secs }),
  closecalls: def('closecalls', { icon: '😱', thresholds: [1, 3, 5, 8, 12], scaled: true, show: (v) => `${Math.round(v)}` }),
  reckless: def('reckless', { icon: '🔥', thresholds: [2, 5, 9, 14, 20], scaled: true, show: (v) => `${Math.round(v)}` }),
  smooth: def('smooth', { icon: '☕', thresholds: [], scaled: false, show: (v) => `${Math.max(1, 5 - Math.floor(v))}★` }),
  ontime: def('ontime', { icon: '⏱️', thresholds: [0.1, 0.2, 0.3, 0.4, 0.5], scaled: false, show: (v) => t('unit.left', { n: Math.round(v * 100) }) }),
};

// What each passenger says when they tell you what they want lives with their lines (src/lines/).

export class Want {
  value = 0; // smooth: penalty points · ontime: fraction left · else: running total
  readonly def: WantDef;
  readonly ask: string;
  private steps: number[];

  // `ask` is how the passenger puts it; `hard` raises every target as the shift's surge climbs (1 = normal).
  constructor(readonly id: WantId, ask: string | undefined, tripSeconds: number, hard = 1) {
    this.def = WANTS[id];
    this.ask = ask ?? this.def.how;
    const k = this.def.scaled ? Math.min(1.5, Math.max(0.7, tripSeconds / 22)) : 1;
    this.steps = this.def.thresholds.map((t) => (id === 'ontime' ? Math.min(0.9, t * hard) : t * k * hard));
    if (id === 'smooth') this.value = 0;
    if (id === 'ontime') this.value = 1;
  }

  // Called every frame of the ride: speed, air and drift fill continuously, so every moment counts.
  tick(dt: number, speed: number, timeLeft: number, airborne: boolean, sliding: boolean) {
    if (this.id === 'speed' && speed > FAST) this.value += dt;
    if (this.id === 'air' && airborne) this.value += dt;
    if (this.id === 'drift' && sliding) this.value += dt;
    if (this.id === 'ontime') this.value = timeLeft;
  }

  // Something happened on the ride. Returns true if this passenger cares.
  feed(kind: Feed, amount = 1): boolean {
    switch (this.id) {
      case 'air': return kind === 'jump'; // the air itself is counted as it happens, in tick()
      case 'drift': return kind === 'drift';
      case 'closecalls': if (kind === 'nearMiss') { this.value += 1; return true; } break;
      case 'reckless': if (kind !== 'drift' && kind !== 'hop') { this.value += kind === 'crash' ? 2 : 1; return true; } break;
      case 'smooth':
        this.value += kind === 'crash' ? (amount > 16 ? 2 : 1) : 0.5;
        return true;
    }
    return false;
  }

  get stars(): number {
    if (this.id === 'smooth') return Math.max(1, 5 - Math.floor(this.value));
    let n = 0;
    for (const s of this.steps) if (this.value >= s) n++;
    return n;
  }

  // 0..1 across the bar of five stars, for the meter.
  get fill(): number {
    if (this.id === 'smooth') return Math.max(0, 5 - this.value) / 5;
    const n = this.stars;
    if (n >= 5) return 1;
    const lo = n === 0 ? 0 : this.steps[n - 1], hi = this.steps[n];
    return (n + Math.min(1, Math.max(0, (this.value - lo) / (hi - lo)))) / 5;
  }

  // The value needed for each star, as the card shows it.
  get targets(): string[] {
    if (this.id === 'smooth') return [];
    return this.steps.map((s) => this.def.show(s));
  }

  get shown(): string { return this.def.show(this.value); }
}
