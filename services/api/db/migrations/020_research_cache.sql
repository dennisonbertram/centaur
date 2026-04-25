-- Research cache: stores TLDR and other research outputs keyed by company identifier.
-- TTL-based: consumers check created_at and decide freshness (default 24h).

-- Up
CREATE TABLE IF NOT EXISTS research_cache (
    id          SERIAL PRIMARY KEY,
    cache_key   TEXT NOT NULL,          -- normalized company identifier (e.g. "tempo.xyz" or "credit.cash")
    cache_type  TEXT NOT NULL DEFAULT 'tldr',  -- type of cached research (tldr, brief, etc.)
    content     TEXT NOT NULL,          -- the full research output
    metadata    JSONB DEFAULT '{}',     -- optional structured data (sector, stage, etc.)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(cache_key, cache_type)
);

CREATE INDEX IF NOT EXISTS idx_research_cache_key ON research_cache(cache_key, cache_type);
CREATE INDEX IF NOT EXISTS idx_research_cache_created ON research_cache(created_at);

-- Down
DROP TABLE IF EXISTS research_cache;
