// The global leaderboard: talks to the Worker at /api/* (worker/index.ts) and draws the panel.
// Under `npm run dev` there's no API, so the board just says it's offline.

import { CABS } from './models';
import { t, type Key } from './i18n';
import { btn, tapButton } from './menus';
import { authHeader } from './account';

export interface Row { initials: string; cab: string; score: number; fares: number; stars: number; seconds: number }
export interface CabStat { cab: string; shifts: number; best: number; average: number; stars: number; holder: string }
export interface Board { top: Row[]; cabs: CabStat[] }
export interface Entry { initials: string; cab: string; score: number; fares: number; stars: number; seconds: number }
export type Posted = { rank: number; cabRank: number } | { error: 'busy' | 'initials' | 'offline' | 'rejected' };

const isJson = (res: Response) => res.headers.get('content-type')?.includes('application/json');
const cache = new Map<string, { at: number; board: Board }>();

export async function fetchBoard(cab = ''): Promise<Board | null> {
  const hit = cache.get(cab);
  if (hit && performance.now() - hit.at < 15_000) return hit.board;
  try {
    const res = await fetch(`/api/leaderboard${cab ? `?cab=${cab}` : ''}`);
    if (!res.ok || !isJson(res)) return null;
    const board = await res.json() as Board;
    cache.set(cab, { at: performance.now(), board });
    return board;
  } catch {
    return null;
  }
}

export async function postScore(entry: Entry): Promise<Posted> {
  try {
    const res = await fetch('/api/scores', { method: 'POST', headers: { 'content-type': 'application/json', ...authHeader() }, body: JSON.stringify(entry) });
    if (res.status === 201) { cache.clear(); return await res.json(); }
    if (res.status === 429) return { error: 'busy' };
    if (!isJson(res) || res.status >= 500) return { error: 'offline' };
    const body = await res.json().catch(() => ({})) as { error?: string };
    return { error: body.error === 'pick other initials' ? 'initials' : 'rejected' };
  } catch {
    return { error: 'offline' };
  }
}

export const cabName = (id: string) => t(`cab.${id}.name` as Key);
const dollars = (cents: number) => '$' + Math.round(cents / 100).toLocaleString('en-US');

// Tab 0 is every cab; tab i is CABS[i - 1]. board: undefined while loading, null when offline.
export function boardHTML(tab: number, board: Board | null | undefined, mine: string) {
  const tabs = ['', ...CABS.map((c) => c.id)].map((id, i) =>
    `<b class="${i === tab ? 'on' : ''}" data-board-tab="${i}">${id ? cabName(id) : t('board.all')}</b>`).join('');
  let top: string;
  if (board === undefined) top = `<p class="note">${t('board.loading')}</p>`;
  else if (board === null) top = `<p class="note">${t('board.offline')}</p>`;
  else if (!board.top.length) top = `<p class="note">${t('board.empty')}</p>`;
  else top = `<table class="top">${board.top.map((r, i) => `
      <tr class="${r.initials === mine ? 'me' : ''}"><td class="n">${i + 1}</td><td class="who">${r.initials}</td>
        ${tab === 0 ? `<td class="cab">${cabName(r.cab)}</td>` : ''}<td class="cash">${dollars(r.score)}</td>
        <td>${t('board.faresN', { n: r.fares })}</td><td>${r.stars ? `${r.stars.toFixed(1)}★` : ''}</td></tr>`).join('')}</table>`;
  // How each cab does, in the order the picker shows them; the best average wears the crown.
  const stats = new Map((board?.cabs ?? []).map((c) => [c.cab, c]));
  const leader = Math.max(0, ...[...stats.values()].map((c) => c.average));
  const cabs = board ? `
    <table class="cabs">
      <tr><th></th><th>${t('board.record')}</th><th>${t('board.average')}</th><th>${t('board.shifts')}</th></tr>
      ${CABS.map((c, i) => {
        const s = stats.get(c.id);
        return `<tr class="${tab === i + 1 ? 'on' : ''}"><td class="cab">${s && s.average === leader ? '👑 ' : ''}${cabName(c.id)}</td>
          <td>${s ? `${dollars(s.best)} <i>${s.holder}</i>` : '—'}</td><td>${s ? dollars(s.average) : '—'}</td><td>${s?.shifts ?? 0}</td></tr>`;
      }).join('')}
    </table>` : '';
  return `
    <div class="board">
      <h3>${t('board.title')}</h3>
      <div class="tabs">${tabs}</div>
      <div class="cols"><div>${top}</div>${cabs ? `<div><h4>${t('board.cabs')}</h4>${cabs}</div>` : ''}</div>
      <div class="board-prompts pad-only">${btn('choose', t('board.tab'))}${btn('back', t('board.back'))}</div>
      <div class="tap-row touch-only">${tapButton('back', t('picker.backTap'))}</div>
    </div>`;
}
