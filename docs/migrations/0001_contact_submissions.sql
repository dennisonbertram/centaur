CREATE TABLE IF NOT EXISTS community_slack_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  interest_reason TEXT NOT NULL,
  invite_status TEXT NOT NULL DEFAULT 'pending',
  source_path TEXT,
  user_agent TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_community_slack_requests_created_at
  ON community_slack_requests (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_community_slack_requests_invite_status
  ON community_slack_requests (invite_status, created_at DESC);
