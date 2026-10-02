# Leaderboard

The leaderboard lives in a Cloudflare D1 (SQLite) database, behind a small Worker
(`worker/index.ts`). Everything else on the site is still a plain static file; only
`/api/*` runs code (`run_worker_first` in `wrangler.jsonc`).

| Database | Used by | id |
| --- | --- | --- |
| `crazy-clankers` | production (crazyclankers.com, workers.dev) | `19e23a6f-…` |
| `crazy-clankers-preview` | preview deploys (Workers Builds) | `95d57b7e-…` |

Previews get their own database because bindings aren't inherited by the `previews`
block, and so testing never touches the real board.

## API

- `GET /api/leaderboard`: the top 10 of all time, plus each cab's record, holder, average and
  number of shifts. Cached for 15 seconds.
- `GET /api/leaderboard?cab=zoox`: the top 10 for one cab.
- `POST /api/scores` with `{ initials, cab, score, fares, stars, seconds }`: `score` is the
  shift's cash in cents. Returns `{ rank, cabRank }`. Five posts a minute per visitor.

The game runs in the browser, so anyone determined can post a fake score. The checks only keep
out junk and floods. If cheating becomes a problem, delete the rows by hand:

```sh
npx wrangler d1 execute crazy-clankers --remote --command "DELETE FROM scores WHERE id = 123"
```

## Changing the table

Add a numbered file to `migrations/`, then apply it to both databases:

```sh
npx wrangler d1 migrations apply crazy-clankers --remote
```

Wrangler only finds databases at the top level of `wrangler.jsonc`, so for the preview database
copy `migrations/` next to a scratch `wrangler.jsonc` that lists `crazy-clankers-preview` as its
only database, and run the same command there with the preview name.

## Running locally

```sh
npx vite build
npx wrangler d1 migrations apply crazy-clankers --local
npx wrangler dev   # the game and the API on http://localhost:8787
```

`npm run dev` (Vite) has no API; the game shows the board as offline there.
