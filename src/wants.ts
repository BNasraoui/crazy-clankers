// What a passenger wants from this ride, and the 1-5 stars they'll give for it.
// Every passenger picks one want per trip from their own pool (passengers.ts).

export type WantId = 'speed' | 'air' | 'drift' | 'closecalls' | 'reckless' | 'smooth' | 'ontime';
export type Feed = 'jump' | 'hop' | 'nearMiss' | 'drift' | 'smash' | 'crash';

interface WantDef {
  title: string;
  how: string; // one line on what counts
  icon: string;
  thresholds: number[]; // value for 1..5 stars, before scaling by trip length
  scaled: boolean; // cumulative over the ride, so longer rides need more
  show: (v: number) => string;
}

export const WANTS: Record<WantId, WantDef> = {
  speed: { title: 'SPEED', how: 'Average speed', icon: '💨', thresholds: [10, 14, 18, 22, 26], scaled: false, show: (v) => `${Math.round(v * 2.237)} mph` },
  air: { title: 'AIR TIME', how: 'Seconds off the ground', icon: '🛫', thresholds: [1, 2.5, 4, 6, 8], scaled: true, show: (v) => `${v.toFixed(1)}s` },
  drift: { title: 'DRIFT', how: 'Seconds sideways', icon: '🌀', thresholds: [1.5, 4, 7, 11, 16], scaled: true, show: (v) => `${v.toFixed(1)}s` },
  closecalls: { title: 'CLOSE CALLS', how: 'Near misses', icon: '😱', thresholds: [1, 3, 5, 8, 12], scaled: true, show: (v) => `${Math.round(v)}` },
  reckless: { title: 'RECKLESS', how: 'Near misses, smashes, jumps and crashes', icon: '🔥', thresholds: [2, 5, 9, 14, 20], scaled: true, show: (v) => `${Math.round(v)}` },
  smooth: { title: 'SMOOTH RIDE', how: 'Every bump, jump or close call costs a star', icon: '☕', thresholds: [], scaled: false, show: (v) => `${Math.max(1, 5 - Math.floor(v))}★` },
  ontime: { title: 'ON TIME', how: 'Time left when you arrive', icon: '⏱️', thresholds: [0.1, 0.2, 0.3, 0.4, 0.5], scaled: false, show: (v) => `${Math.round(v * 100)}% left` },
};

// What each passenger says when they tell you what they want.
export const ASKS: Record<string, Partial<Record<WantId, string>>> = {
  techbro: { speed: 'Move fast. Literally.', air: 'Do a sick jump. For the vlog.', closecalls: 'Thread the needle, bro.' },
  cmo: { air: "Get some air. I'm filming.", drift: 'Drift it. Slow-mo is on.' },
  ceo: { speed: "I'm late. Which means you're late.", reckless: 'Disrupt something.', ontime: 'Every second costs me $40,000.' },
  founder: { reckless: 'Move fast and break things.', speed: 'Runway is short. Go.' },
  rocket: { air: 'To Mars. Or at least up.', speed: 'Faster. This is Plaid, right?' },
  safety: { smooth: 'Gently. I have a paper due on alignment.', reckless: 'I need evidence these models are dangerous. Show me.' },
  sweater: { smooth: 'Please. I just need one calm thing today.' },
};

export class Want {
  value = 0; // speed: average m/s · smooth: penalty points · ontime: fraction left · else: running total
  private dist = 0;
  private time = 0;
  readonly def: WantDef;
  readonly ask: string;
  private steps: number[];

  constructor(readonly id: WantId, passenger: string, tripSeconds: number) {
    this.def = WANTS[id];
    this.ask = ASKS[passenger]?.[id] ?? this.def.how;
    const k = this.def.scaled ? Math.min(1.5, Math.max(0.7, tripSeconds / 22)) : 1;
    this.steps = this.def.thresholds.map((t) => t * k);
    if (id === 'smooth') this.value = 0;
    if (id === 'ontime') this.value = 1;
  }

  // Called every frame of the ride.
  tick(dt: number, speed: number, timeLeft: number) {
    if (this.id === 'speed') {
      this.dist += speed * dt;
      this.time += dt;
      this.value = this.time > 0 ? this.dist / this.time : 0;
    }
    if (this.id === 'ontime') this.value = timeLeft;
  }

  // Something happened on the ride. Returns true if this passenger cares.
  feed(kind: Feed, amount = 1): boolean {
    switch (this.id) {
      case 'air': if (kind === 'jump') { this.value += amount; return true; } break;
      case 'drift': if (kind === 'drift') { this.value += amount; return true; } break;
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
