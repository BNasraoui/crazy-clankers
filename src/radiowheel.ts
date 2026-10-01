import type { Input } from './input';

// The station wheel, GTA style: hold LB (or T) and the stations fan out round the
// screen while the game slows; aim with the right stick (or left/right) and let go
// to tune. A quick tap just skips to the next station.

const HOLD = 0.22; // seconds held before the wheel opens

export interface WheelItem { name: string; disabled?: boolean }

export class RadioWheel {
  private held = 0;
  private open = false;
  private items: WheelItem[] = [];
  private pick = 0;
  private el = document.createElement('div');

  constructor() {
    this.el.id = 'radio-wheel';
    this.el.hidden = true;
    document.body.appendChild(this.el);
  }

  get isOpen() { return this.open; }

  // Returns the chosen item's index on release, 'tap' for a quick press, or null.
  update(dt: number, input: Input, items: () => WheelItem[], current: number): number | 'tap' | null {
    if (input.radioHold) {
      this.held += dt;
      if (!this.open && this.held >= HOLD) {
        this.items = items();
        this.pick = Math.max(0, Math.min(this.items.length - 1, current));
        this.open = true;
        this.render();
      }
      if (this.open) this.steer(input);
      return null;
    }
    const wasOpen = this.open, held = this.held;
    this.held = 0;
    if (wasOpen) {
      this.open = false;
      this.el.hidden = true;
      return this.items[this.pick]?.disabled ? null : this.pick;
    }
    return held > 0 ? 'tap' : null;
  }

  private steer(input: Input) {
    const n = this.items.length;
    let pick = this.pick;
    if (Math.hypot(input.aimX, input.aimY) > 0.5) {
      // Item 0 sits at the top; the rest go round clockwise.
      const angle = (Math.atan2(input.aimX, -input.aimY) + Math.PI * 2) % (Math.PI * 2);
      pick = Math.round(angle / ((Math.PI * 2) / n)) % n;
    }
    if (input.navX) pick = (pick + input.navX + n) % n;
    if (pick !== this.pick && !this.items[pick]?.disabled) {
      this.pick = pick;
      this.render();
    }
  }

  private render() {
    const n = this.items.length;
    const r = 34; // % of the wheel's size
    this.el.innerHTML = `<div class="ring">${this.items.map((it, i) => {
      const a = (i / n) * Math.PI * 2;
      const x = 50 + r * Math.sin(a), y = 50 - r * Math.cos(a);
      const cls = `${i === this.pick ? 'on' : ''} ${it.disabled ? 'off' : ''}`;
      return `<div class="slot ${cls}" style="left:${x.toFixed(1)}%;top:${y.toFixed(1)}%">${escape(it.name)}</div>`;
    }).join('')}<div class="hub"><small>📻 CLANKERS FM</small><b>${escape(this.items[this.pick]?.name ?? '')}</b><small>release to tune</small></div></div>`;
    this.el.hidden = false;
  }
}

const escape = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);
