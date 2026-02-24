"""PostHog plugin tools — works both as imported plugin and standalone."""
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

from .client import PostHogClient


def _client() -> PostHogClient:
    return PostHogClient(
        api_key=secret("POSTHOG_API_KEY"),
        project_id=secret("POSTHOG_PROJECT_ID"),
    )


@plugin_tool(name="posthog_query")
def query(sql: str) -> dict:
    """Execute a HogQL query against PostHog.

    Args:
        sql: HogQL SQL query
    """
    return _client().query(sql)


@plugin_tool(name="posthog_pageviews")
def pageviews(url_pattern: str | None = None, days: int = 7, limit: int = 20) -> dict:
    """Get pageview analytics.

    Args:
        url_pattern: Filter URLs containing this pattern
        days: Number of days to look back
        limit: Max results
    """
    return _client().pageviews(url_pattern=url_pattern, days=days, limit=limit)


@plugin_tool(name="posthog_breakdown")
def breakdown(
    property: str = "$browser",
    event: str | None = None,
    days: int = 7,
    limit: int = 20,
) -> dict:
    """Get event breakdown by a property.

    Args:
        property: Property to breakdown by (e.g., '$browser', '$os')
        event: Event name to filter
        days: Number of days to look back
        limit: Max results
    """
    return _client().breakdown(event=event, property=property, days=days, limit=limit)


@plugin_tool(name="posthog_user_agents")
def user_agents(
    url_pattern: str | None = None,
    days: int = 7,
    limit: int = 20,
) -> dict:
    """Get user-agent breakdown (browser + OS).

    Args:
        url_pattern: Filter URLs containing this pattern
        days: Number of days to look back
        limit: Max results
    """
    return _client().user_agents(url_pattern=url_pattern, days=days, limit=limit)
