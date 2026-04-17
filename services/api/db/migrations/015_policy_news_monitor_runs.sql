-- migrate:up

CREATE TABLE IF NOT EXISTS policy_news_monitor_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    slack_channel_id TEXT NOT NULL DEFAULT '',
    enabled_source_count INTEGER NOT NULL DEFAULT 0,
    fetch_successes INTEGER NOT NULL DEFAULT 0,
    fetch_failures INTEGER NOT NULL DEFAULT 0,
    new_articles INTEGER NOT NULL DEFAULT 0,
    classified_candidates INTEGER NOT NULL DEFAULT 0,
    alertable_clusters INTEGER NOT NULL DEFAULT 0,
    alerts_sent INTEGER NOT NULL DEFAULT 0,
    feedback_commands INTEGER NOT NULL DEFAULT 0,
    query_replies INTEGER NOT NULL DEFAULT 0,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    last_post_attempt JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_text TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_policy_news_monitor_runs_started
    ON policy_news_monitor_runs (started_at DESC);

-- migrate:down

DROP TABLE IF EXISTS policy_news_monitor_runs;
