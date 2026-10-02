import { babble } from './audio';
import { lang } from './i18n';
import type { WantId } from './wants';
import * as cab from './lines/cab';
import * as techbro from './lines/techbro';
import * as cmo from './lines/cmo';
import * as ceo from './lines/ceo';
import * as founder from './lines/founder';
import * as sweater from './lines/sweater';
import * as rocket from './lines/rocket';
import * as safety from './lines/safety';

export type Speaker = 'cab' | 'techbro' | 'cmo' | 'ceo' | 'founder' | 'sweater' | 'rocket' | 'safety';
export type QuipEvent =
  | 'pickup' | 'dropoff' | 'walkout' | 'idle'
  | 'jump' | 'jumpFirst' | 'nearMiss' | 'crash' | 'drift' | 'slow' | 'timeLow'
  | 'fired' | 'back' | 'reroute' | 'safetyLow'
  | 'dash' | 'smash' | 'geyser' | 'underwater' | 'bigAir' | 'pedDive' | 'timber'
  | 'surge' | 'ram' | 'carpool' | 'premium'
  | `good.${WantId}` | `bad.${WantId}`; // how the ride is going for what they want

export type Lines = Partial<Record<QuipEvent, string[]>>;
export type Asks = { en: Partial<Record<WantId, string>>; zh: Partial<Record<WantId, string>> };

export const SPEAKERS: Record<Speaker, { color: string; pitch: number }> = {
  cab: { color: '#14a892', pitch: 880 },
  techbro: { color: '#2f6fd6', pitch: 300 },
  cmo: { color: '#e0458f', pitch: 620 },
  ceo: { color: '#d6332b', pitch: 220 },
  founder: { color: '#e07b1a', pitch: 420 },
  sweater: { color: '#6b6f76', pitch: 360 },
  rocket: { color: '#222222', pitch: 260 },
  safety: { color: '#c86f3c', pitch: 400 },
};

// Edit freely in src/lines/: lines are picked from a shuffled bag, so every line plays
// once before any repeats. "{dest}" is replaced with a place name.
const FILES = { cab, techbro, cmo, ceo, founder, sweater, rocket, safety };
const lines = (speaker: Speaker, event: QuipEvent) => (lang() === 'zh' ? FILES[speaker].zh : FILES[speaker].en)[event];

// What a passenger says when they tell you what they want, in the current language.
export function askLine(speaker: Speaker, want: WantId): string | undefined {
  const f = FILES[speaker] as { asks?: Asks };
  return f.asks?.[lang()][want];
}

// A speech bubble's time on screen: Chinese packs about three letters' worth into each character.
const readTime = (text: string) => Math.min(5, Math.max(2.2, 1.4 + text.length * (lang() === 'zh' ? 0.16 : 0.05)));

const PRIORITY: Partial<Record<QuipEvent, number>> = {
  pickup: 3, dropoff: 3, walkout: 3, fired: 3, back: 3, reroute: 3, underwater: 3, jumpFirst: 2,
  crash: 2, safetyLow: 2, geyser: 2, bigAir: 2, jump: 1, nearMiss: 1, timeLow: 1, dash: 1,
};
const CHANCE: Partial<Record<QuipEvent, number>> = { jump: 0.8, nearMiss: 0.6, drift: 0.4, crash: 0.9, idle: 0.7, dash: 0.35, smash: 0.25 };

// `who` is the rider's name tag ("Name · Role"); the cab's is filled in by the game.
export type ShowQuip = (speaker: Speaker, color: string, text: string, seconds: number, who?: string) => void;
type SayOpts = { delay?: number; vars?: Record<string, string>; force?: boolean; who?: string };

export class QuipDirector {
  private bags = new Map<string, string[]>();
  private last = new Map<string, string>();
  private busyUntil = 0;
  private busyPriority = -1;
  private lastAt = -10;
  private queue: { at: number; speaker: Speaker; event: QuipEvent; opts: SayOpts }[] = [];
  now = 0;

  constructor(private show: ShowQuip) {}

  say(speaker: Speaker, event: QuipEvent, opts: SayOpts = {}) {
    if (!lines(speaker, event)) return false;
    if (!opts.force && Math.random() > (CHANCE[event] ?? 1)) return false;
    if (opts.delay) {
      this.queue.push({ at: this.now + opts.delay, speaker, event, opts: { ...opts, delay: 0 } });
      return true;
    }
    const pri = PRIORITY[event] ?? 0;
    if (this.now < this.busyUntil && pri <= this.busyPriority && pri < 3) return false;
    if (pri < 2 && this.now - this.lastAt < 1.2) return false;
    let text = this.draw(speaker, event);
    for (const [k, v] of Object.entries(opts.vars ?? {})) text = text.replaceAll(`{${k}}`, v);
    const seconds = readTime(text);
    const s = SPEAKERS[speaker];
    this.show(speaker, s.color, text, seconds, opts.who);
    babble(text, s.pitch);
    this.busyUntil = this.now + seconds;
    this.busyPriority = pri;
    this.lastAt = this.now;
    return true;
  }

  // A one-off line not drawn from the bags (what a passenger wants from the ride).
  line(speaker: Speaker, text: string, who?: string) {
    const seconds = readTime(text);
    const s = SPEAKERS[speaker];
    this.show(speaker, s.color, text, seconds, who);
    babble(text, s.pitch);
    this.busyUntil = this.now + seconds;
    this.busyPriority = 3;
    this.lastAt = this.now;
  }

  update(now: number) {
    this.now = now;
    const due = this.queue.filter((q) => q.at <= now);
    this.queue = this.queue.filter((q) => q.at > now);
    for (const q of due) this.say(q.speaker, q.event, { ...q.opts, force: true });
  }

  reset() {
    this.queue = [];
    this.busyUntil = 0;
  }

  private draw(speaker: Speaker, event: QuipEvent) {
    const key = `${lang()}.${speaker}.${event}`;
    let bag = this.bags.get(key);
    if (!bag || bag.length === 0) {
      bag = [...lines(speaker, event)!].sort(() => Math.random() - 0.5);
      if (bag.length > 1 && bag[bag.length - 1] === this.last.get(key)) bag.unshift(bag.pop()!);
      this.bags.set(key, bag);
    }
    const line = bag.pop()!;
    this.last.set(key, line);
    return line;
  }
}
