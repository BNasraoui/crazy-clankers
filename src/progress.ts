// Per-cab progress, kept on this device: XP and level, personal best, shifts driven.
// Every shift earns XP for the cab you drove; levels are what will unlock each cab's story missions.

const STORE = 'clankers.progress';
const INITIALS = 'clankers.initials';

export interface CabProgress { xp: number; best: number; shifts: number } // best: cash in cents
export const LEVEL_CAP = 10;

// Total XP to reach a level: 0, 200, 600, 1200, 2000 ... (each level takes 200 more than the last).
export const xpForLevel = (level: number) => 100 * level * (level - 1);

export function levelOf(xp: number) {
  let level = 1;
  while (level < LEVEL_CAP && xp >= xpForLevel(level + 1)) level++;
  return level;
}

// How far into the current level, 0..1 (1 at the cap).
export function levelFill(xp: number) {
  const level = levelOf(xp);
  if (level >= LEVEL_CAP) return 1;
  const from = xpForLevel(level), to = xpForLevel(level + 1);
  return (xp - from) / (to - from);
}

// A shift's XP: 10 a fare, plus 5 for every star a passenger gave.
export const shiftXp = (fares: number, stars: number[]) => fares * 10 + stars.reduce((s, n) => s + n * 5, 0);

function load(): Record<string, Partial<CabProgress>> {
  try { return JSON.parse(localStorage.getItem(STORE) ?? '{}') ?? {}; } catch { return {}; }
}

export function progressOf(cab: string): CabProgress {
  return { xp: 0, best: 0, shifts: 0, ...load()[cab] };
}

export interface ShiftResult { gained: number; before: CabProgress; after: CabProgress; best: boolean }

export function recordShift(cab: string, fares: number, stars: number[], cents: number): ShiftResult {
  const all = load() as Record<string, CabProgress>;
  const before = progressOf(cab);
  const gained = shiftXp(fares, stars);
  const after = { xp: before.xp + gained, best: Math.max(before.best, cents), shifts: before.shifts + 1 };
  all[cab] = after;
  try { localStorage.setItem(STORE, JSON.stringify(all)); } catch { /* storage unavailable */ }
  return { gained, before, after, best: cents > before.best && before.shifts > 0 };
}

export function savedInitials() {
  try { return localStorage.getItem(INITIALS) ?? ''; } catch { return ''; }
}
export function saveInitials(initials: string) {
  try { localStorage.setItem(INITIALS, initials); } catch { /* storage unavailable */ }
}
