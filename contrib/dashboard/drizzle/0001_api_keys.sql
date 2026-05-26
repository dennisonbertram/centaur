CREATE TABLE IF NOT EXISTS api_keys (
  id TEXT PRIMARY KEY,
  deployment_id TEXT NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
  key_prefix TEXT NOT NULL,
  key_hash TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL DEFAULT 'Default',
  pending_value TEXT,
  reveal_value TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  last_used_at TIMESTAMP,
  revoked_at TIMESTAMP,
  revocation_pushed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS api_keys_deployment_active_idx
  ON api_keys (deployment_id, created_at)
  WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS api_keys_revocation_pending_idx
  ON api_keys (deployment_id, revoked_at)
  WHERE revoked_at IS NOT NULL AND revocation_pushed_at IS NULL;
