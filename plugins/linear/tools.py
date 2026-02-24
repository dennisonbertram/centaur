"""Linear plugin tools — works both as imported plugin and standalone."""

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


from .client import LinearClient


def _client() -> LinearClient:
    return LinearClient(api_key=secret("LINEAR_API_KEY"))


async def _in_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.get_event_loop().run_in_executor(
        None, functools.partial(fn, *args, **kwargs)
    )


@plugin_tool()
async def issues(
    team_key: str | None = None,
    assignee: str | None = None,
    state: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List Linear issues with optional filters.

    Args:
        team_key: Filter by team key (e.g., "ENG")
        assignee: Filter by assignee name or "me"
        state: Filter by state name (e.g., "In Progress", "Done")
        limit: Max results
    """
    client = _client()
    return await _in_thread(
        client.issues, team_key=team_key, assignee=assignee, state=state, limit=limit
    )


@plugin_tool()
async def issue(issue_id: str) -> dict:
    """Get a single Linear issue by ID or identifier (e.g., ENG-123).

    Args:
        issue_id: Issue ID or identifier
    """
    client = _client()
    return await _in_thread(client.issue, issue_id)


@plugin_tool()
async def create_issue(
    title: str,
    team_id: str,
    description: str | None = None,
    assignee_id: str | None = None,
    priority: int | None = None,
) -> dict:
    """Create a new Linear issue.

    Args:
        title: Issue title
        team_id: Team ID
        description: Issue description
        assignee_id: Assignee user ID
        priority: Priority (0=none, 1=urgent, 2=high, 3=medium, 4=low)
    """
    client = _client()
    return await _in_thread(
        client.create_issue,
        title=title,
        team_id=team_id,
        description=description,
        assignee_id=assignee_id,
        priority=priority,
    )


@plugin_tool()
async def update_issue(
    issue_id: str,
    title: str | None = None,
    description: str | None = None,
    state_id: str | None = None,
    assignee_id: str | None = None,
    priority: int | None = None,
) -> dict:
    """Update an existing Linear issue.

    Args:
        issue_id: Issue ID or identifier
        title: New title
        description: New description
        state_id: New state ID
        assignee_id: New assignee user ID
        priority: New priority (0-4)
    """
    client = _client()
    return await _in_thread(
        client.update_issue,
        issue_id=issue_id,
        title=title,
        description=description,
        state_id=state_id,
        assignee_id=assignee_id,
        priority=priority,
    )


@plugin_tool()
async def search_issues(query: str, limit: int = 25) -> list[dict]:
    """Search Linear issues by text.

    Args:
        query: Search query
        limit: Max results
    """
    client = _client()
    return await _in_thread(client.search_issues, query, limit=limit)


@plugin_tool()
async def projects(limit: int = 50) -> list[dict]:
    """List all Linear projects.

    Args:
        limit: Max results
    """
    client = _client()
    return await _in_thread(client.projects, limit=limit)


@plugin_tool()
async def project(project_id: str) -> dict:
    """Get a single Linear project.

    Args:
        project_id: Project ID
    """
    client = _client()
    return await _in_thread(client.project, project_id)


@plugin_tool()
async def teams(limit: int = 50) -> list[dict]:
    """List all Linear teams.

    Args:
        limit: Max results
    """
    client = _client()
    return await _in_thread(client.teams, limit=limit)


@plugin_tool()
async def cycles(team_key: str | None = None, limit: int = 20) -> list[dict]:
    """List Linear cycles, optionally filtered by team.

    Args:
        team_key: Filter by team key
        limit: Max results
    """
    client = _client()
    return await _in_thread(client.cycles, team_key=team_key, limit=limit)


@plugin_tool()
async def add_comment(issue_id: str, body: str) -> dict:
    """Add a comment to a Linear issue.

    Args:
        issue_id: Issue ID or identifier
        body: Comment text (markdown supported)
    """
    client = _client()
    return await _in_thread(client.add_comment, issue_id, body)
