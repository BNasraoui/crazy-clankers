// Logging in, which is optional: Google through Shoo (https://shoo.dev), so a player's XP follows
// them between devices. The page leaves for Google and comes back, so the game only offers it on
// the results screen, once the shift is already saved. The server (worker/index.ts) checks Shoo's
// token once and gives us its own session, which is all we keep.

import { createShooAuth } from '@shoojs/auth';
import { allProgress, replaceProgress, type CabProgress } from './progress';

const SESSION = 'clankers.session';
const PENDING = 'clankers.pending'; // shifts that haven't reached the server yet
const CALLBACK = '/auth/callback';

const auth = createShooAuth({ shooBaseUrl: 'https://shoo.dev', callbackPath: CALLBACK, fallbackPath: '/' });

interface Shift { cab: string; xp: number; cents: number }
type Progress = Record<string, CabProgress>;

const read = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string | null) => {
  try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* storage unavailable */ }
};
const pending = (): Shift[] => { try { return JSON.parse(read(PENDING) ?? '[]'); } catch { return []; } };

export const loggedIn = () => !!read(SESSION);

export function logIn() {
  return auth.startSignIn({ returnTo: '/' }); // leaves the page
}

export function logOut() {
  write(SESSION, null);
  write(PENDING, null);
  auth.clearIdentity();
}

async function api(method: string, path: string, body?: unknown) {
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  const session = read(SESSION);
  if (session) headers.authorization = `Bearer ${session}`;
  return fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
}

export const authHeader = (): Record<string, string> => {
  const session = read(SESSION);
  return session ? { authorization: `Bearer ${session}` } : {};
};

// On every page load: finish a login that's coming back from Google, else bring this device up to date.
// Resolves to 'in' when a login just finished, 'failed' when one didn't, otherwise null.
export async function syncAccount(): Promise<'in' | 'failed' | null> {
  if (location.pathname === CALLBACK) {
    let result: 'in' | 'failed' = 'failed';
    try {
      const token = await auth.finishSignIn({ redirectAfter: false });
      if (token?.id_token) {
        const res = await api('POST', '/api/login', { token: token.id_token, progress: allProgress() });
        if (res.ok) {
          const { session, progress } = await res.json() as { session: string; progress: Progress };
          write(SESSION, session);
          write(PENDING, null); // the login just counted everything on this device
          replaceProgress(progress);
          result = 'in';
        }
      }
    } catch (error) {
      console.warn('Login failed:', error);
    }
    auth.clearIdentity(); // Shoo's token has done its job
    history.replaceState(null, '', '/');
    return result;
  }
  if (loggedIn() && (await flush())) {
    try {
      const res = await api('GET', '/api/me');
      if (res.status === 401) logOut();
      else if (res.ok) replaceProgress(((await res.json()) as { progress: Progress }).progress);
    } catch { /* offline: this device's copy will do */ }
  }
  return null;
}

// A finished shift's XP, for the account. Kept until the server has it.
export async function pushShift(shift: Shift) {
  if (!loggedIn()) return;
  write(PENDING, JSON.stringify([...pending(), shift]));
  await flush();
}

// Send waiting shifts, oldest first. True when none are left.
async function flush() {
  const queue = pending();
  while (queue.length) {
    try {
      const res = await api('POST', '/api/me/shift', queue[0]);
      if (res.status === 401) { logOut(); return false; }
      if (!res.ok) return false; // try again next time
      queue.shift();
      write(PENDING, JSON.stringify(queue));
      if (!queue.length) replaceProgress(((await res.json()) as { progress: Progress }).progress);
    } catch {
      return false;
    }
  }
  return true;
}
