"""Research cache — stores and retrieves TLDR briefs and other research outputs.

Backed by the Centaur Postgres database. Keyed by company identifier + type.
Default TTL is 24 hours — callers get the cached result if fresh, or empty if stale.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


API_BASE = "http://api:8000"


class ResearchCacheClient:
    """Cache for research outputs (TLDR briefs, company data, etc.)."""

    def _query(self, sql: str) -> list[dict]:
        """Execute a SQL query against the Centaur API database."""
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{API_BASE}/tools/paradigmdb/db_query",
                json={"query": sql, "limit": 1},
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("result", [])

    def get(self, company: str, cache_type: str = "tldr", max_age_hours: int = 24) -> dict:
        """Retrieve a cached research result if it exists and is fresh.

        Args:
            company: Company identifier (domain preferred, e.g. "tempo.xyz", or name)
            cache_type: Type of research ("tldr", "brief", etc.)
            max_age_hours: Maximum age in hours before the cache is considered stale (default 24)

        Returns: dict with "found" bool, "content" str, "metadata" dict, "age_hours" float.
                 If not found or stale, "found" is False and "content" is empty.
        """
        key = company.lower().strip().rstrip("/")
        # Strip protocol if present
        for prefix in ("https://", "http://", "www."):
            if key.startswith(prefix):
                key = key[len(prefix):]

        sql = f"""
            SELECT content, metadata, created_at
            FROM research_cache
            WHERE cache_key = '{key.replace("'", "''")}'
              AND cache_type = '{cache_type.replace("'", "''")}'
              AND created_at > NOW() - INTERVAL '{max_age_hours} hours'
            ORDER BY created_at DESC
            LIMIT 1
        """
        rows = self._query(sql)
        if not rows:
            return {"found": False, "content": "", "metadata": {}, "age_hours": None}

        row = rows[0]
        created = row.get("created_at", "")
        age_hours = None
        if created:
            try:
                created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                age_hours = round((datetime.now(timezone.utc) - created_dt).total_seconds() / 3600, 1)
            except (ValueError, TypeError):
                pass

        return {
            "found": True,
            "content": row.get("content", ""),
            "metadata": row.get("metadata", {}),
            "age_hours": age_hours,
        }

    def put(self, company: str, content: str, cache_type: str = "tldr", metadata: dict | None = None) -> dict:
        """Store a research result in the cache. Overwrites any existing entry for the same key+type.

        Args:
            company: Company identifier (domain preferred, e.g. "tempo.xyz", or name)
            content: The full research output to cache
            cache_type: Type of research ("tldr", "brief", etc.)
            metadata: Optional structured data (sector, stage, is_portfolio, etc.)

        Returns: dict with "status" and "cache_key"
        """
        key = company.lower().strip().rstrip("/")
        for prefix in ("https://", "http://", "www."):
            if key.startswith(prefix):
                key = key[len(prefix):]

        escaped_content = content.replace("'", "''")
        escaped_key = key.replace("'", "''")
        escaped_type = cache_type.replace("'", "''")
        meta_json = "{}" if not metadata else str(metadata).replace("'", "''")

        # Try importing json for proper serialization
        import json
        meta_json = json.dumps(metadata or {}).replace("'", "''")

        sql = f"""
            INSERT INTO research_cache (cache_key, cache_type, content, metadata)
            VALUES ('{escaped_key}', '{escaped_type}', '{escaped_content}', '{meta_json}'::jsonb)
            ON CONFLICT (cache_key, cache_type)
            DO UPDATE SET content = EXCLUDED.content,
                          metadata = EXCLUDED.metadata,
                          created_at = NOW()
            RETURNING id
        """
        try:
            self._query(sql)
            return {"status": "cached", "cache_key": key}
        except Exception as e:
            return {"status": "error", "error": str(e), "cache_key": key}

    def invalidate(self, company: str, cache_type: str = "tldr") -> dict:
        """Delete a cached entry.

        Args:
            company: Company identifier
            cache_type: Type of research to invalidate
        """
        key = company.lower().strip().rstrip("/")
        for prefix in ("https://", "http://", "www."):
            if key.startswith(prefix):
                key = key[len(prefix):]

        sql = f"""
            DELETE FROM research_cache
            WHERE cache_key = '{key.replace("'", "''")}'
              AND cache_type = '{cache_type.replace("'", "''")}'
        """
        try:
            self._query(sql)
            return {"status": "invalidated", "cache_key": key}
        except Exception as e:
            return {"status": "error", "error": str(e)}


def _client() -> ResearchCacheClient:
    return ResearchCacheClient()
