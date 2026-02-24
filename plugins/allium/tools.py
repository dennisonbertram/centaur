"""Allium plugin tools — works both as imported plugin and standalone."""

from __future__ import annotations

import os
from typing import Any

try:
    from ai_v2.plugin_sdk import plugin_tool, secret
except ImportError:

    def plugin_tool(*, name: str | None = None):  # type: ignore[misc]
        def decorator(fn: Any) -> Any:
            fn.__plugin_tool__ = name or fn.__name__
            return fn
        return decorator

    def secret(key: str, default: str | None = None) -> str:  # type: ignore[misc]
        val = os.environ.get(key)
        if val:
            return val
        if default is not None:
            return default
        raise KeyError(f"Missing env var '{key}'")

from .client import AlliumClient


def _client() -> AlliumClient:
    return AlliumClient(api_key=secret("ALLIUM_API_KEY"))


@plugin_tool()
async def run_sql(sql: str, row_limit: int = 10000) -> list[dict]:
    """Execute arbitrary SQL directly against Allium.

    Uses the MCP endpoint for direct SQL execution.

    Args:
        sql: SQL query to execute
        row_limit: Maximum rows to return (default 10000, max 250000)
    """
    client = _client()
    try:
        return client.run_sql(sql, row_limit=row_limit)
    finally:
        client.close()


@plugin_tool()
async def search_schemas(query: str) -> list[str]:
    """Search Allium schemas using semantic search.

    Args:
        query: Search query (e.g., "erc20 token transfers")
    """
    client = _client()
    try:
        return client.search_schemas(query)
    finally:
        client.close()


@plugin_tool()
async def fetch_schema(table_id: str) -> dict:
    """Fetch schema metadata for a table.

    Args:
        table_id: Full table name (e.g., "ethereum.raw.token_transfers")
    """
    client = _client()
    try:
        return client.fetch_schema(table_id)
    finally:
        client.close()
