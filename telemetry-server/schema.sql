-- Escriba telemetry — one row per anonymous usage ping.
-- Stores only what PRIVACY.md discloses; no audio, transcripts, or personal data.

CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  install_id  TEXT NOT NULL,                       -- anonymous random id
  event       TEXT NOT NULL,                       -- e.g. 'transcription_complete'
  minutes     REAL DEFAULT 0,                      -- minutes of audio processed
  version     TEXT,                                -- app version
  created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);
CREATE INDEX IF NOT EXISTS idx_events_install ON events(install_id);
