---
name: paradigm-memory
description: "Query Paradigm's internal knowledge base (Slack, GitHub, Linear, GCal, Gmail, etc.). Use when asked about internal discussions, team activity, people, PRs, issues, or company knowledge."
---

# Paradigm Memory

Query the Paradigm AI v2 knowledge base via REST API. This indexes Slack, GitHub, Linear, GCal, Gmail, GDrive, Granola, Attio, Pylon, and BetterStack.

## Setup

The API runs at `http://206.223.235.69:8000`. Auth is via Bearer token stored in `~/.config/agents/skills/paradigm-memory/.env`.

If `.env` doesn't exist, ask the user for the API key and create it:
```
PARADIGM_MEMORY_URL=http://206.223.235.69:8000
PARADIGM_MEMORY_KEY=<key>
```

## Commands

All commands go through the `scripts/memory.sh` wrapper:

```bash
# Search across all sources (hybrid semantic + keyword)
scripts/memory.sh search "reth storage backend"
scripts/memory.sh search "uniswap v4 hooks" --sources slack,github

# Run read-only SQL against raw_records / embeddings
scripts/memory.sh sql "SELECT source, kind, count(*) FROM raw_records GROUP BY source, kind"

# Timeline of recent activity
scripts/memory.sh timeline                    # last 7 days
scripts/memory.sh timeline --days 30          # last 30 days
scripts/memory.sh timeline --source github    # only github

# People
scripts/memory.sh people                      # list all
scripts/memory.sh person georgios             # get person + identities

# Slack
scripts/memory.sh slack-messages --channel C001 --text "deploy"
scripts/memory.sh slack-threads --channel C001

# GitHub PRs
scripts/memory.sh github-prs --author gakonst --state open

# Linear issues
scripts/memory.sh linear-issues --state "In Progress"

# Sources and sync
scripts/memory.sh sources                     # list sources + counts
scripts/memory.sh sync-status                 # sync cursor state
scripts/memory.sh sync-runs                   # recent sync runs
scripts/memory.sh health                      # API + DB health
```

## Workflow

1. **Broad search**: `scripts/memory.sh search "topic"` to find relevant records
2. **Drill down**: Use source-specific queries (slack-messages, github-prs, linear-issues)
3. **SQL for custom queries**: `scripts/memory.sh sql "SELECT ..."` for anything not covered by endpoints
4. **People lookup**: `scripts/memory.sh person <slug>` to find cross-source identities

## Tips

- Search hits the `embeddings` table (requires OPENAI_API_KEY for vector search). If embeddings aren't populated yet, use `sql` to query `raw_records` directly.
- SQL queries are read-only — INSERT/UPDATE/DELETE/DROP are blocked.
- The `raw_records` table stores everything as JSONB in the `data` column. Use `data->>'field'` to extract fields.
