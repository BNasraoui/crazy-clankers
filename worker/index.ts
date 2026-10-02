// The game's server: the static build (dist/), plus the leaderboard at /api/*.
// Scores live in a D1 (SQLite) database; the table is in migrations/. Previews use their own
// scratch database (wrangler.jsonc), so testing never touches the real board.
//
//   GET  /api/leaderboard          top 10 of all time, plus each cab's record, average and shift count
//   GET  /api/leaderboard?cab=zoox top 10 for one cab
//   POST /api/scores               { initials, cab, score, fares, stars, seconds } → { rank, cabRank }
//   POST /api/login                { token, progress } → { session, progress }   (token: Shoo's ID token)
//   GET  /api/me                   → { progress }                                 (Authorization: Bearer <session>)
//   POST /api/me/shift             { cab, xp, cents } → { progress }
//
// The game runs in the browser, so a determined cheat can post any score. The checks below only
// keep out junk and floods; anything cleverer would need the server to replay the shift.

interface D1Statement {
  bind(...values: unknown[]): D1Statement;
  first<T>(): Promise<T | null>;
  all<T>(): Promise<{ results: T[] }>;
  run(): Promise<unknown>;
}
interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
  DB: { prepare(sql: string): D1Statement; batch(statements: D1Statement[]): Promise<{ results: unknown[] }[]> };
  SUBMIT?: { limit(options: { key: string }): Promise<{ success: boolean }> };
  SESSION_KEY?: string; // secret (wrangler secret put SESSION_KEY): signs our session tokens
}

const CABS = ['wayfarer', 'cybercab', 'zoox', 'apollo'];
// Three-letter tags nobody should see on a public board.
const BLOCKED = new Set(['ASS', 'CUM', 'CNT', 'COK', 'DIK', 'FAG', 'FCK', 'FUC', 'FUK', 'FKU', 'KKK', 'KYS', 'NGR', 'NIG', 'SEX', 'SHT', 'TIT', 'WTF', 'XXX']);

const json = (body: unknown, status = 200, cache = 'no-store') =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', 'cache-control': cache } });
const fail = (error: string, status = 400) => json({ error }, status);

const int = (v: unknown, min: number, max: number) => (typeof v === 'number' && Number.isInteger(v) && v >= min && v <= max ? v : null);
const num = (v: unknown, min: number, max: number) => (typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max ? v : null);

async function leaderboard(env: Env, cab: string | null) {
  if (cab !== null && !CABS.includes(cab)) return fail('unknown cab');
  const top = cab
    ? env.DB.prepare('SELECT initials, cab, score, fares, stars, seconds, created FROM scores WHERE cab = ? ORDER BY score DESC, created LIMIT 10').bind(cab)
    : env.DB.prepare('SELECT initials, cab, score, fares, stars, seconds, created FROM scores ORDER BY score DESC, created LIMIT 10');
  const cabs = env.DB.prepare(`
    SELECT cab, COUNT(*) AS shifts, MAX(score) AS best, CAST(ROUND(AVG(score)) AS INTEGER) AS average, ROUND(AVG(stars), 2) AS stars,
      (SELECT initials FROM scores b WHERE b.cab = a.cab ORDER BY score DESC, created LIMIT 1) AS holder
    FROM scores a GROUP BY cab`);
  const [t, c] = await env.DB.batch([top, cabs]);
  return json({ top: t.results, cabs: c.results }, 200, 'public, max-age=15');
}

async function limited(request: Request, env: Env) {
  const ip = request.headers.get('cf-connecting-ip') ?? 'local';
  return !!env.SUBMIT && !(await env.SUBMIT.limit({ key: ip })).success;
}

async function submit(request: Request, env: Env) {
  if (await limited(request, env)) return fail('slow down', 429);
  let body: Record<string, unknown>;
  try { body = await request.json(); } catch { return fail('bad json'); }
  const initials = typeof body.initials === 'string' ? body.initials.toUpperCase() : '';
  if (!/^[A-Z0-9]{3}$/.test(initials)) return fail('initials are three letters or digits');
  if (BLOCKED.has(initials)) return fail('pick other initials');
  const cab = typeof body.cab === 'string' && CABS.includes(body.cab) ? body.cab : null;
  const score = int(body.score, 0, 100_000_000); // cents: up to $1M
  const fares = int(body.fares, 1, 500); // a shift with no fares doesn't make the board
  const stars = num(body.stars, 0, 5);
  const seconds = int(body.seconds, 1, 4 * 3600);
  if (cab === null || score === null || fares === null || stars === null || seconds === null) return fail('bad score');
  const player = await sessionPlayer(request, env); // a logged-in player's score remembers them
  await env.DB.prepare('INSERT INTO scores (initials, cab, score, fares, stars, seconds, created, player) VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
    .bind(initials, cab, score, fares, Math.round(stars * 100) / 100, seconds, Math.floor(Date.now() / 1000), player).run();
  const [all, mine] = await env.DB.batch([
    env.DB.prepare('SELECT COUNT(*) AS n FROM scores WHERE score > ?').bind(score),
    env.DB.prepare('SELECT COUNT(*) AS n FROM scores WHERE cab = ? AND score > ?').bind(cab, score),
  ]);
  const n = (r: { results: unknown[] }) => (r.results[0] as { n: number }).n;
  return json({ rank: n(all) + 1, cabRank: n(mine) + 1 }, 201);
}

// ---------- accounts ----------
// Logging in is Google, through Shoo (https://shoo.dev): the game sends Shoo's ID token here once,
// we check it against Shoo's public keys and hand back our own session token (the player id signed
// with SESSION_KEY). So Shoo is needed to log in, never to stay logged in.

const SHOO = 'https://shoo.dev';
type Progress = Record<string, { xp: number; best: number; shifts: number }>;

const utf8 = new TextEncoder();
const fromB64 = (s: string) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
const toB64 = (bytes: ArrayBuffer | Uint8Array) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const parse = (part: string) => JSON.parse(new TextDecoder().decode(fromB64(part)));

let shooKeys: { at: number; keys: (JsonWebKey & { kid?: string })[] } | null = null;
async function shooKey(kid: string) {
  for (const fresh of [false, true]) { // a key we haven't seen: fetch again in case Shoo rotated
    if (fresh || !shooKeys || Date.now() - shooKeys.at > 3600_000) {
      const res = await fetch(`${SHOO}/.well-known/jwks.json`);
      if (!res.ok) throw new Error(`Shoo keys: ${res.status}`);
      shooKeys = { at: Date.now(), keys: ((await res.json()) as { keys: (JsonWebKey & { kid?: string })[] }).keys };
    }
    const key = shooKeys.keys.find((k) => k.kid === kid);
    if (key) return key;
  }
  return null;
}

// Shoo's ID token (an ES256 JWT) → the player's id on this site, or null if anything is off.
async function shooPlayer(token: string, origin: string): Promise<string | null> {
  const [head, body, sig] = token.split('.');
  if (!head || !body || !sig) return null;
  const header = parse(head) as { alg?: string; kid?: string };
  if (header.alg !== 'ES256' || !header.kid) return null;
  const jwk = await shooKey(header.kid);
  if (!jwk) return null;
  const key = await crypto.subtle.importKey('jwk', { kty: jwk.kty, crv: jwk.crv, x: jwk.x, y: jwk.y }, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
  if (!(await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, key, fromB64(sig), utf8.encode(`${head}.${body}`)))) return null;
  const claims = parse(body) as { iss?: string; aud?: string | string[]; exp?: number; pairwise_sub?: string };
  const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (claims.iss !== SHOO || !aud.includes(`origin:${origin}`)) return null; // issued for this site only
  if (typeof claims.exp !== 'number' || claims.exp < Date.now() / 1000 - 60) return null;
  return typeof claims.pairwise_sub === 'string' && claims.pairwise_sub ? claims.pairwise_sub : null;
}

const hmacKey = (env: Env) =>
  crypto.subtle.importKey('raw', utf8.encode(env.SESSION_KEY!), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);

async function makeSession(env: Env, player: string) {
  const id = toB64(utf8.encode(player));
  return `${id}.${toB64(await crypto.subtle.sign('HMAC', await hmacKey(env), utf8.encode(id)))}`;
}

// The logged-in player behind "Authorization: Bearer <session>", or null.
async function sessionPlayer(request: Request, env: Env): Promise<string | null> {
  const token = request.headers.get('authorization')?.match(/^Bearer (\S+)$/)?.[1];
  if (!token || !env.SESSION_KEY) return null;
  const [id, sig] = token.split('.');
  if (!id || !sig) return null;
  try {
    if (!(await crypto.subtle.verify('HMAC', await hmacKey(env), fromB64(sig), utf8.encode(id)))) return null;
    return new TextDecoder().decode(fromB64(id));
  } catch {
    return null;
  }
}

// Progress from a client: only known cabs, only sane whole numbers.
function cleanProgress(raw: unknown): Progress {
  const out: Progress = {};
  if (!raw || typeof raw !== 'object') return out;
  for (const cab of CABS) {
    const p = (raw as Record<string, Record<string, unknown>>)[cab];
    if (!p || typeof p !== 'object') continue;
    const xp = int(p.xp, 0, 10_000_000), best = int(p.best, 0, 100_000_000), shifts = int(p.shifts, 0, 1_000_000);
    if (xp !== null && best !== null && shifts !== null) out[cab] = { xp, best, shifts };
  }
  return out;
}

async function loadProgress(env: Env, player: string): Promise<Progress> {
  const row = await env.DB.prepare('SELECT progress FROM players WHERE id = ?').bind(player).first<{ progress: string }>();
  return row ? cleanProgress(JSON.parse(row.progress)) : {};
}

async function saveProgress(env: Env, player: string, progress: Progress) {
  const now = Math.floor(Date.now() / 1000);
  await env.DB.prepare('INSERT INTO players (id, progress, created, updated) VALUES (?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET progress = excluded.progress, updated = excluded.updated')
    .bind(player, JSON.stringify(progress), now, now).run();
}

async function login(request: Request, env: Env) {
  if (!env.SESSION_KEY) return fail('logins are off', 503);
  if (await limited(request, env)) return fail('slow down', 429);
  let body: { token?: unknown; progress?: unknown };
  try { body = await request.json(); } catch { return fail('bad json'); }
  if (typeof body.token !== 'string' || body.token.length > 4096) return fail('bad token');
  const player = await shooPlayer(body.token, new URL(request.url).origin);
  if (!player) return fail('bad token', 401);
  // This device's progress joins the account's: the larger of each, so logging in twice never counts a shift twice.
  const progress = await loadProgress(env, player);
  for (const [cab, p] of Object.entries(cleanProgress(body.progress))) {
    const q = progress[cab] ?? { xp: 0, best: 0, shifts: 0 };
    progress[cab] = { xp: Math.max(p.xp, q.xp), best: Math.max(p.best, q.best), shifts: Math.max(p.shifts, q.shifts) };
  }
  await saveProgress(env, player, progress);
  return json({ session: await makeSession(env, player), progress });
}

async function me(request: Request, env: Env) {
  const player = await sessionPlayer(request, env);
  if (!player) return fail('log in', 401);
  return json({ progress: await loadProgress(env, player) });
}

async function shift(request: Request, env: Env) {
  const player = await sessionPlayer(request, env);
  if (!player) return fail('log in', 401);
  if (await limited(request, env)) return fail('slow down', 429);
  let body: Record<string, unknown>;
  try { body = await request.json(); } catch { return fail('bad json'); }
  const cab = typeof body.cab === 'string' && CABS.includes(body.cab) ? body.cab : null;
  const xp = int(body.xp, 0, 20_000), cents = int(body.cents, 0, 100_000_000);
  if (cab === null || xp === null || cents === null) return fail('bad shift');
  const progress = await loadProgress(env, player);
  const p = progress[cab] ?? { xp: 0, best: 0, shifts: 0 };
  progress[cab] = { xp: p.xp + xp, best: Math.max(p.best, cents), shifts: p.shifts + 1 };
  await saveProgress(env, player, progress);
  return json({ progress });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/')) return env.ASSETS.fetch(request);
    try {
      if (url.pathname === '/api/leaderboard' && request.method === 'GET') return await leaderboard(env, url.searchParams.get('cab'));
      if (url.pathname === '/api/scores' && request.method === 'POST') return await submit(request, env);
      if (url.pathname === '/api/login' && request.method === 'POST') return await login(request, env);
      if (url.pathname === '/api/me' && request.method === 'GET') return await me(request, env);
      if (url.pathname === '/api/me/shift' && request.method === 'POST') return await shift(request, env);
      return fail('not found', 404);
    } catch (error) {
      console.error(error);
      return fail('server error', 500);
    }
  },
};
