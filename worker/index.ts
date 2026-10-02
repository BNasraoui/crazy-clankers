// The game's server: the static build (dist/), plus the leaderboard at /api/*.
// Scores live in a D1 (SQLite) database; the table is in migrations/. Previews use their own
// scratch database (wrangler.jsonc), so testing never touches the real board.
//
//   GET  /api/leaderboard          top 10 of all time, plus each cab's record, average and shift count
//   GET  /api/leaderboard?cab=zoox top 10 for one cab
//   POST /api/scores               { initials, cab, score, fares, stars, seconds } → { rank, cabRank }
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

async function submit(request: Request, env: Env) {
  const ip = request.headers.get('cf-connecting-ip') ?? 'local';
  if (env.SUBMIT && !(await env.SUBMIT.limit({ key: ip })).success) return fail('slow down', 429);
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
  await env.DB.prepare('INSERT INTO scores (initials, cab, score, fares, stars, seconds, created) VALUES (?, ?, ?, ?, ?, ?, ?)')
    .bind(initials, cab, score, fares, Math.round(stars * 100) / 100, seconds, Math.floor(Date.now() / 1000)).run();
  const [all, mine] = await env.DB.batch([
    env.DB.prepare('SELECT COUNT(*) AS n FROM scores WHERE score > ?').bind(score),
    env.DB.prepare('SELECT COUNT(*) AS n FROM scores WHERE cab = ? AND score > ?').bind(cab, score),
  ]);
  const n = (r: { results: unknown[] }) => (r.results[0] as { n: number }).n;
  return json({ rank: n(all) + 1, cabRank: n(mine) + 1 }, 201);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/')) return env.ASSETS.fetch(request);
    try {
      if (url.pathname === '/api/leaderboard' && request.method === 'GET') return await leaderboard(env, url.searchParams.get('cab'));
      if (url.pathname === '/api/scores' && request.method === 'POST') return await submit(request, env);
      return fail('not found', 404);
    } catch (error) {
      console.error(error);
      return fail('server error', 500);
    }
  },
};
