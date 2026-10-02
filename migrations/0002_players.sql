-- Players who logged in (Google, through Shoo) so their XP follows them between devices.
-- id is Shoo's pairwise subject: a stable id for this player on this site, not their Google id.
-- progress is JSON: { "<cab id>": { "xp": n, "best": cents, "shifts": n }, ... }
CREATE TABLE players (
  id TEXT PRIMARY KEY,
  progress TEXT NOT NULL DEFAULT '{}',
  created INTEGER NOT NULL,
  updated INTEGER NOT NULL
);
-- Scores signed while logged in remember who signed them.
ALTER TABLE scores ADD COLUMN player TEXT;
