// The leaderboard and account API (worker/index.ts), run in Node: `npm run test:api`.
// Shoo is stood in for by a key made here, and D1 by Node's built-in SQLite with the real migrations.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import worker from '../../worker/index.ts';

const ORIGIN = 'https://crazyclankers.com';
const sqlite = new DatabaseSync(':memory:');
for (const f of readdirSync('migrations').sort()) sqlite.exec(readFileSync(`migrations/${f}`, 'utf8'));

// Just enough of D1's interface.
const stmt = (sql: string, args: unknown[] = []) => ({
  bind: (...v: unknown[]) => stmt(sql, v),
  first: async () => sqlite.prepare(sql).get(...(args as never[])) ?? null,
  all: async () => ({ results: sqlite.prepare(sql).all(...(args as never[])) }),
  run: async () => sqlite.prepare(sql).run(...(args as never[])),
});
const env = {
  DB: { prepare: (sql: string) => stmt(sql), batch: (s: ReturnType<typeof stmt>[]) => Promise.all(s.map((x) => x.all())) },
  ASSETS: { fetch: async () => new Response('static') },
  SESSION_KEY: 'test-key',
};

// A stand-in Shoo: our own ES256 key, served as Shoo's JWKS.
const pair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
const jwk = { ...(await crypto.subtle.exportKey('jwk', pair.publicKey)), kid: 'test-1', alg: 'ES256' };
const realFetch = globalThis.fetch;
globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) =>
  String(url) === 'https://shoo.dev/.well-known/jwks.json' ? Response.json({ keys: [jwk] }) : realFetch(url, init)) as typeof fetch;

const b64 = (b: ArrayBuffer | Uint8Array | string) =>
  Buffer.from(typeof b === 'string' ? b : new Uint8Array(b)).toString('base64url');
async function idToken(claims: Record<string, unknown>, kid = 'test-1') {
  const head = b64(JSON.stringify({ alg: 'ES256', kid })), body = b64(JSON.stringify(claims));
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, pair.privateKey, new TextEncoder().encode(`${head}.${body}`));
  return `${head}.${body}.${b64(sig)}`;
}
const good = (sub = 'player-1') => idToken({ iss: 'https://shoo.dev', aud: `origin:${ORIGIN}`, exp: Date.now() / 1000 + 600, pairwise_sub: sub });

async function call(method: string, path: string, body?: unknown, session?: string) {
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (session) headers.authorization = `Bearer ${session}`;
  const res = await worker.fetch(new Request(ORIGIN + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(typeof body === 'string' ? body : body) }), env as never);
  return { status: res.status, body: await res.json().catch(() => null) as any };
}

test('scores: valid posts rank, junk is refused', async () => {
  const entry = { initials: 'abc', cab: 'zoox', score: 120000, fares: 10, stars: 4.5, seconds: 200 };
  assert.deepEqual((await call('POST', '/api/scores', entry)).body, { rank: 1, cabRank: 1 });
  assert.equal((await call('POST', '/api/scores', { ...entry, initials: 'KKK' })).status, 400);
  assert.equal((await call('POST', '/api/scores', { ...entry, cab: 'tesla' })).status, 400);
  assert.equal((await call('POST', '/api/scores', { ...entry, fares: 0 })).status, 400);
  assert.equal((await call('POST', '/api/scores', { ...entry, score: 1.5 })).status, 400);
  const board = (await call('GET', '/api/leaderboard')).body;
  assert.equal(board.top[0].initials, 'ABC');
  assert.equal(board.cabs[0].holder, 'ABC');
});

test('login: only a genuine Shoo token for this site gets a session', async () => {
  const now = Date.now() / 1000;
  const bad = [
    await idToken({ iss: 'https://evil.dev', aud: `origin:${ORIGIN}`, exp: now + 600, pairwise_sub: 'x' }),
    await idToken({ iss: 'https://shoo.dev', aud: 'origin:https://other.site', exp: now + 600, pairwise_sub: 'x' }),
    await idToken({ iss: 'https://shoo.dev', aud: `origin:${ORIGIN}`, exp: now - 3600, pairwise_sub: 'x' }),
    await idToken({ iss: 'https://shoo.dev', aud: `origin:${ORIGIN}`, exp: now + 600 }),
    await idToken({ iss: 'https://shoo.dev', aud: `origin:${ORIGIN}`, exp: now + 600, pairwise_sub: 'x' }, 'unknown-kid'),
  ];
  const t = await good();
  bad.push(t.slice(0, -4) + (t.endsWith('AAAA') ? 'BBBB' : 'AAAA')); // tampered signature
  const [h, , s] = t.split('.');
  bad.push(`${h}.${b64(JSON.stringify({ iss: 'https://shoo.dev', aud: `origin:${ORIGIN}`, exp: now + 600, pairwise_sub: 'someone-else' }))}.${s}`); // swapped claims
  for (const token of bad) assert.equal((await call('POST', '/api/login', { token })).status, 401);
  assert.equal((await call('GET', '/api/me', undefined, 'forged.session')).status, 401);
  assert.equal((await call('GET', '/api/me')).status, 401);
});

test('progress: login merges, shifts add up, another device sees it', async () => {
  const first = await call('POST', '/api/login', { token: await good('p2'), progress: { zoox: { xp: 300, best: 5000, shifts: 2 }, tesla: { xp: 9 } } });
  assert.equal(first.status, 200);
  assert.deepEqual(first.body.progress, { zoox: { xp: 300, best: 5000, shifts: 2 } });
  const session = first.body.session;
  const after = await call('POST', '/api/me/shift', { cab: 'zoox', xp: 120, cents: 9000 }, session);
  assert.deepEqual(after.body.progress.zoox, { xp: 420, best: 9000, shifts: 3 });
  assert.equal((await call('POST', '/api/me/shift', { cab: 'zoox', xp: 999999, cents: 1 }, session)).status, 400);
  // A second device with less progress logs in: nothing goes backwards, nothing counts twice.
  const second = await call('POST', '/api/login', { token: await good('p2'), progress: { zoox: { xp: 100, best: 100, shifts: 1 }, apollo: { xp: 50, best: 10, shifts: 1 } } });
  assert.deepEqual(second.body.progress, { zoox: { xp: 420, best: 9000, shifts: 3 }, apollo: { xp: 50, best: 10, shifts: 1 } });
  assert.deepEqual((await call('GET', '/api/me', undefined, second.body.session)).body.progress, second.body.progress);
  // A score signed while logged in is tied to the player.
  await call('POST', '/api/scores', { initials: 'PTW', cab: 'zoox', score: 9000, fares: 3, stars: 4, seconds: 100 }, session);
  assert.equal((sqlite.prepare("SELECT player FROM scores WHERE initials = 'PTW'").get() as { player: string }).player, 'p2');
});

test('logins switch off cleanly without a SESSION_KEY', async () => {
  const key = env.SESSION_KEY;
  (env as { SESSION_KEY?: string }).SESSION_KEY = undefined;
  assert.equal((await call('POST', '/api/login', { token: await good() })).status, 503);
  env.SESSION_KEY = key;
});
