"""DDL for SQLite. Applied via init_db (CREATE IF NOT EXISTS)."""

SCHEMA_VERSION = 1

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS mappings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  webset_id TEXT NOT NULL UNIQUE,
  ashby_job_id TEXT NOT NULL,
  source_tag TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  exa_webhook_id TEXT,
  candidates_pushed_count INTEGER NOT NULL DEFAULT 0 CHECK (candidates_pushed_count >= 0),
  last_sync_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mappings_active ON mappings(active);

CREATE TABLE IF NOT EXISTS pushed_candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  webset_id TEXT NOT NULL,
  exa_item_id TEXT,
  candidate_email TEXT,
  candidate_linkedin_url TEXT,
  ashby_candidate_id TEXT NOT NULL,
  pushed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pushed_webset ON pushed_candidates(webset_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pushed_webset_exa_item
  ON pushed_candidates(webset_id, exa_item_id)
  WHERE exa_item_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pushed_webset_email
  ON pushed_candidates(webset_id, candidate_email)
  WHERE candidate_email IS NOT NULL AND length(trim(candidate_email)) > 0;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pushed_webset_li
  ON pushed_candidates(webset_id, candidate_linkedin_url)
  WHERE candidate_linkedin_url IS NOT NULL AND length(trim(candidate_linkedin_url)) > 0;

CREATE TABLE IF NOT EXISTS activity_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL DEFAULT (datetime('now')),
  event_type TEXT NOT NULL,
  webset_id TEXT,
  details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(timestamp DESC);
"""
