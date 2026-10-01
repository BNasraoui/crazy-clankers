// Manga moments: a split-second freeze with a comic-panel burst and a big sound
// word on the hardest hits, and slow motion at the top of a big jump.

const WORDS = {
  crash: [['ドカーン', 'KRAKOOM!'], ['ガシャーン', 'GASHAAN!'], ['バキッ', 'BAKKK!'], ['ドゴォ', 'DOGOOO!']],
  land: [['ズドン', 'ZUDOOM!'], ['ドスン', 'THOOM!'], ['ドーン', 'DOOOON!']],
} as const;
export type Moment = keyof typeof WORDS;

export class Moments {
  private stop = 0; // seconds of near-freeze left (real time)
  private slow = 0; // seconds of slow motion left (real time)
  private slowFor = 1;
  private scale = 1;
  private lastPanel = -9;
  private el: HTMLDivElement;

  constructor() {
    this.el = document.createElement('div');
    this.el.id = 'moment';
    document.getElementById('hud')?.appendChild(this.el);
  }

  // How fast the game runs this frame (1 = normal), given the real frame time.
  timeScale(dt: number) {
    let want = 1;
    if (this.stop > 0) {
      this.stop -= dt;
      want = 0.04;
    } else if (this.slow > 0) {
      this.slow -= dt;
      // Ease out of the slow motion over its last third.
      const t = this.slow / this.slowFor;
      want = 0.3 + 0.7 * Math.max(0, 1 - t * 3);
    }
    // Snap into a freeze, ease out of it.
    this.scale = want < this.scale ? want : this.scale + (want - this.scale) * Math.min(1, dt * 12);
    return this.scale;
  }

  slowMotion(seconds: number) {
    if (this.slow > 0 || this.stop > 0) return;
    this.slow = this.slowFor = seconds;
  }

  // The freeze plus the panel; rate-limited so a pile-up doesn't strobe.
  panel(kind: Moment, strength = 1) {
    const now = performance.now() / 1000;
    if (now - this.lastPanel < 1.2) return;
    this.lastPanel = now;
    this.stop = 0.09 + 0.06 * Math.min(1, strength);
    this.slow = 0;
    const words = WORDS[kind];
    const [jp, en] = words[Math.floor(Math.random() * words.length)];
    const tilt = (Math.random() * 14 - 7).toFixed(1);
    this.el.className = '';
    this.el.innerHTML = `<div class="focus ${kind}"></div><div class="sfx" style="--tilt:${tilt}deg"><span class="jp">${jp}</span><span class="en">${en}</span></div>`;
    void this.el.offsetWidth; // restart the animation
    this.el.className = 'on';
  }
}
