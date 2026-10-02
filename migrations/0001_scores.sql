-- One row per finished shift that the player signed with their initials.
-- score is the shift's cash in cents; stars is the average rating fares gave (0 when none did).
CREATE TABLE scores (
  id INTEGER PRIMARY KEY,
  initials TEXT NOT NULL,
  cab TEXT NOT NULL,
  score INTEGER NOT NULL,
  fares INTEGER NOT NULL,
  stars REAL NOT NULL,
  seconds INTEGER NOT NULL,
  created INTEGER NOT NULL -- unix seconds
);
CREATE INDEX scores_by_score ON scores (score DESC);
CREATE INDEX scores_by_cab ON scores (cab, score DESC);
