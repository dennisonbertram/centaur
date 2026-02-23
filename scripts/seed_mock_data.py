"""Seed mock data for testing the MCP server."""
import asyncio
import hashlib
import json

import asyncpg


async def seed():
    pool = await asyncpg.create_pool(
        "postgresql://tempo:tempo_dev@localhost:5432/ai_v2", min_size=1, max_size=2
    )
    async with pool.acquire() as conn:
        # People
        await conn.executemany(
            """
            INSERT INTO people (slug, name, email, role, focus_area)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (slug) DO NOTHING
            """,
            [
                ("georgios", "Georgios Konstantopoulos", "georgios@paradigm.xyz", "CTO", "protocol engineering"),
                ("dan", "Dan Robinson", "dan@paradigm.xyz", "Research Partner", "DeFi mechanisms"),
                ("frankie", "Frankie", "frankie@paradigm.xyz", "Research Engineer", "MEV and searchers"),
            ],
        )

        # Entity mappings
        await conn.executemany(
            """
            INSERT INTO entity_mappings (source, external_id, person_slug)
            VALUES ($1, $2, $3)
            ON CONFLICT (source, external_id) DO NOTHING
            """,
            [
                ("slack", "U001", "georgios"),
                ("github", "gakonst", "georgios"),
                ("slack", "U002", "dan"),
                ("github", "danrobinson", "dan"),
                ("slack", "U003", "frankie"),
            ],
        )

        # Slack messages
        slack_msgs = [
            {"channel": "C001", "channel_name": "engineering", "user": "U001", "text": "We need to ship the new reth storage backend by end of week. The trie benchmarks are looking good.", "ts": "1708900000.000100", "thread_ts": "1708900000.000100"},
            {"channel": "C001", "channel_name": "engineering", "user": "U003", "text": "Agreed. I have the parallel state root PR ready for review. Getting 2x speedup on mainnet sync.", "ts": "1708900100.000200", "thread_ts": "1708900000.000100"},
            {"channel": "C001", "channel_name": "engineering", "user": "U001", "text": "Nice! Can you also benchmark against Geth 1.14? We need comparative numbers for the blog post.", "ts": "1708900200.000300", "thread_ts": "1708900000.000100"},
            {"channel": "C002", "channel_name": "deals", "user": "U002", "text": "Had a great call with the Uniswap team about v4 hooks. They are thinking about intent-based routing.", "ts": "1708901000.000100", "thread_ts": "1708901000.000100"},
            {"channel": "C002", "channel_name": "deals", "user": "U002", "text": "Follow up: they want to explore a grant for MEV-aware hook implementations. Frankie should take a look.", "ts": "1708901100.000200", "thread_ts": "1708901000.000100"},
            {"channel": "C003", "channel_name": "general", "user": "U001", "text": "Team offsite confirmed for March 15-17 in Denver. Please book flights ASAP.", "ts": "1708902000.000100"},
        ]
        for msg in slack_msgs:
            ch = hashlib.sha256(json.dumps(msg, sort_keys=True).encode()).hexdigest()[:16]
            await conn.execute(
                "INSERT INTO raw_records (source, kind, external_id, content_hash, data) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                "slack", "message", f"slack-{msg['ts']}", ch, json.dumps(msg),
            )

        # GitHub PRs
        gh_prs = [
            {"title": "feat: parallel state root computation", "html_url": "https://github.com/paradigmxyz/reth/pull/1234", "user": {"login": "gakonst"}, "state": "open", "body": "Implements parallel state root computation using rayon. 2x speedup on mainnet sync.", "number": 1234},
            {"title": "fix: trie prefetch race condition", "html_url": "https://github.com/paradigmxyz/reth/pull/1235", "user": {"login": "frankie"}, "state": "merged", "body": "Fixes a race condition in trie prefetch that caused occasional panics during sync.", "number": 1235},
            {"title": "docs: update storage backend benchmarks", "html_url": "https://github.com/paradigmxyz/reth/pull/1236", "user": {"login": "gakonst"}, "state": "open", "body": "Updated benchmark results comparing reth vs geth storage performance.", "number": 1236},
        ]
        for pr in gh_prs:
            ch = hashlib.sha256(json.dumps(pr, sort_keys=True).encode()).hexdigest()[:16]
            await conn.execute(
                "INSERT INTO raw_records (source, kind, external_id, content_hash, data) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                "github", "pull_request", f"reth-{pr['number']}", ch, json.dumps(pr),
            )

        # Linear issues
        linear_issues = [
            {"title": "Ship reth 1.2 release", "url": "https://linear.app/paradigm/issue/ENG-100", "state": {"name": "In Progress"}, "assignee": {"name": "Georgios"}, "priority": 1, "description": "Prepare and ship reth 1.2 with parallel state root and new storage backend."},
            {"title": "MEV-aware hook research", "url": "https://linear.app/paradigm/issue/RES-50", "state": {"name": "Todo"}, "assignee": {"name": "Frankie"}, "priority": 2, "description": "Research MEV-aware hooks for Uniswap v4. Write up findings."},
        ]
        for issue in linear_issues:
            issue_id = issue["url"].split("/")[-1]
            ch = hashlib.sha256(json.dumps(issue, sort_keys=True).encode()).hexdigest()[:16]
            await conn.execute(
                "INSERT INTO raw_records (source, kind, external_id, content_hash, data) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                "linear", "issue", f"linear-{issue_id}", ch, json.dumps(issue),
            )

        # Sync cursors
        await conn.executemany(
            "INSERT INTO sync_cursors (cursor_key, source, kind, cursor) VALUES ($1, $2, $3, $4) ON CONFLICT (cursor_key) DO NOTHING",
            [
                ("slack:message", "slack", "message", "1708902000"),
                ("github:pull_request", "github", "pull_request", "2024-02-25T00:00:00Z"),
                ("linear:issue", "linear", "issue", "2024-02-25T00:00:00Z"),
            ],
        )

        # Sync runs
        await conn.executemany(
            "INSERT INTO sync_runs (source, status, started_at, finished_at, records_synced) VALUES ($1, $2, NOW() - INTERVAL '1 hour', NOW() - INTERVAL '59 minutes', $3)",
            [("slack", "completed", 6), ("github", "completed", 3), ("linear", "completed", 2)],
        )

        counts = await conn.fetch(
            "SELECT source, kind, count(*) as n FROM raw_records GROUP BY source, kind ORDER BY source"
        )
        print("Seeded raw_records:")
        for r in counts:
            print(f"  {r['source']}/{r['kind']}: {r['n']}")
        people_count = await conn.fetchval("SELECT count(*) FROM people")
        print(f"People: {people_count}")
        print("Done!")

    await pool.close()


asyncio.run(seed())
