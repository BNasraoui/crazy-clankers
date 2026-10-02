// Logging in, which is optional: Google through Shoo (https://shoo.dev), so a player's XP follows
// them between devices. Google opens in a popup and the game stays put: Google sends the popup
// back to /auth (public/auth.html), which hands the code over and closes. If the popup is blocked
// (or there was no click to open it from, like a pad button), the whole page goes instead and
// comes back to the title. The server (worker/index.ts) checks Shoo's token once and gives us
// its own session, which is all we keep.

import { createShooAuth } from '@shoojs/auth';
import { allProgress, replaceProgress, type CabProgress } from './progress';

const SESSION = 'clankers.session';
const PENDING = 'clankers.pending'; // shifts that haven't reached the server yet
const SHOO = 'https://shoo.dev';
const REDIRECT = `${location.origin}/auth`;

const auth = createShooAuth({ shooBaseUrl: SHOO, redirectUri: REDIRECT, fallbackPath: '/' });

interface Shift { cab: string; xp: number; cents: number }
type Progress = Record<string, CabProgress>;

const read = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string | null) => {
  try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* storage unavailable */ }
};
const pending = (): Shift[] => { try { return JSON.parse(read(PENDING) ?? '[]'); } catch { return []; } };

export const loggedIn = () => !!read(SESSION);

// Must run straight from a click or tap: browsers only allow popups then.
// Resolves 'in' or 'failed' (a popup that's closed without logging in just never resolves).
export function logIn(): Promise<'in' | 'failed'> {
  try { sessionStorage.removeItem('clankers.loginMode'); } catch { /* fine */ }
  const popup = window.open('about:blank', 'clankers-login', 'popup,width=500,height=680');
  if (!popup) {
    try { sessionStorage.setItem('clankers.loginMode', 'redirect'); } catch { /* fine */ }
    void auth.startSignIn({ returnTo: '/' }); // leaves the page
    return new Promise(() => {});
  }
  return (async () => {
    const pkce = await auth.createPkceBundle();
    popup.location.href = auth.createSignInUrl({ state: pkce.state, codeChallenge: pkce.challenge });
    const reply = await new Promise<{ code?: string; state?: string }>((resolve) => {
      const channel = new BroadcastChannel('clankers-login');
      channel.onmessage = (e) => {
        if (e.data?.state !== pkce.state) return; // an older attempt's popup
        channel.close();
        resolve(e.data);
      };
    });
    if (!reply.code) return 'failed';
    try {
      const token = await auth.exchangeCode({ shooBaseUrl: SHOO, clientId: `origin:${location.origin}`, redirectUri: REDIRECT, code: reply.code, codeVerifier: pkce.verifier });
      return (await finishLogin(token.id_token)) ? 'in' : 'failed';
    } catch (error) {
      console.warn('Login failed:', error);
      return 'failed';
    }
  })();
}

// Shoo's ID token → our session, with this device's progress joining the account's.
async function finishLogin(idToken: string) {
  const res = await api('POST', '/api/login', { token: idToken, progress: allProgress() });
  if (!res.ok) return false;
  const { session, progress } = await res.json() as { session: string; progress: Progress };
  write(SESSION, session);
  write(PENDING, null); // the login just counted everything on this device
  replaceProgress(progress);
  return true;
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

// On every page load: finish a whole-page login that's coming back from Google, else bring this
// device up to date. Resolves to 'in' when a login just finished, 'failed' when one didn't, otherwise null.
export async function syncAccount(): Promise<'in' | 'failed' | null> {
  if (auth.parseCallback()) {
    let result: 'in' | 'failed' = 'failed';
    try {
      const token = await auth.finishSignIn({ redirectAfter: false });
      if (token?.id_token && (await finishLogin(token.id_token))) result = 'in';
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
