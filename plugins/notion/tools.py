"""Notion plugin tools — works both as imported plugin and standalone."""

from __future__ import annotations

import asyncio
import functools
import os
from typing import Any

# --- Plugin registration (no-op if ai_v2 not installed) ---
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


from .client import NotionClient


def _client() -> NotionClient:
    return NotionClient(api_key=secret("NOTION_API_KEY"))


async def _in_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.get_event_loop().run_in_executor(
        None, functools.partial(fn, *args, **kwargs)
    )


@plugin_tool()
async def search(
    query: str | None = None,
    filter_type: str | None = None,
    page_size: int = 25,
) -> dict:
    """Search Notion pages and databases by title.

    Args:
        query: Text to search for in titles
        filter_type: 'page' or 'database' to filter results
        page_size: Results per page (max 100)
    """
    client = _client()
    return await _in_thread(
        client.search, query=query, filter_type=filter_type, page_size=page_size
    )


@plugin_tool()
async def get_page(page_id: str) -> dict:
    """Retrieve a Notion page by ID.

    Args:
        page_id: Page ID
    """
    client = _client()
    return await _in_thread(client.page, page_id)


@plugin_tool()
async def get_page_content(page_id: str) -> list[dict]:
    """Get all block children of a page (full content).

    Args:
        page_id: Page ID
    """
    client = _client()
    return await _in_thread(client.get_page_content, page_id)


@plugin_tool()
async def query_database(
    database_id: str,
    filter: dict | None = None,
    sorts: list[dict] | None = None,
    page_size: int = 100,
) -> dict:
    """Query a Notion database.

    Args:
        database_id: Database ID
        filter: Filter object (see Notion docs)
        sorts: Sort objects (see Notion docs)
        page_size: Results per page (max 100)
    """
    client = _client()
    return await _in_thread(
        client.query_database,
        database_id,
        filter=filter,
        sorts=sorts,
        page_size=page_size,
    )


@plugin_tool()
async def create_page(
    parent: dict,
    properties: dict,
    children: list[dict] | None = None,
) -> dict:
    """Create a Notion page.

    Args:
        parent: Parent object (e.g., {"database_id": "..."} or {"page_id": "..."})
        properties: Page properties
        children: Initial block children
    """
    client = _client()
    return await _in_thread(
        client.create_page, parent, properties, children=children
    )


@plugin_tool()
async def update_page(
    page_id: str,
    properties: dict | None = None,
    archived: bool | None = None,
) -> dict:
    """Update a Notion page.

    Args:
        page_id: Page ID
        properties: Updated properties
        archived: Set to True to archive, False to restore
    """
    client = _client()
    return await _in_thread(
        client.update_page, page_id, properties=properties, archived=archived
    )


@plugin_tool()
async def get_database(database_id: str) -> dict:
    """Retrieve a Notion database schema and metadata.

    Args:
        database_id: Database ID
    """
    client = _client()
    return await _in_thread(client.database, database_id)


@plugin_tool()
async def append_blocks(
    block_id: str,
    children: list[dict],
) -> dict:
    """Append blocks to a page or block.

    Args:
        block_id: Parent block/page ID
        children: Block objects to append
    """
    client = _client()
    return await _in_thread(client.append_block_children, block_id, children)


@plugin_tool()
async def add_comment(page_id: str, text: str) -> dict:
    """Add a comment to a Notion page.

    Args:
        page_id: Page ID
        text: Comment text
    """
    client = _client()
    return await _in_thread(
        client.create_comment,
        parent={"page_id": page_id},
        rich_text=NotionClient.make_rich_text(text),
    )
