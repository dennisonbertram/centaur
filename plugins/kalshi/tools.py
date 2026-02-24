"""Kalshi plugin tools — works both as imported plugin and standalone."""
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

from .client import KalshiClient


def _client() -> KalshiClient:
    return KalshiClient()


@plugin_tool(name="kalshi_list_markets")
def list_markets(
    status: str = "open",
    event_ticker: str | None = None,
    limit: int = 20,
) -> dict:
    """List Kalshi prediction markets.

    Args:
        status: Filter by status (open, closed, settled)
        event_ticker: Filter by event ticker
        limit: Max results
    """
    return _client().list_markets(
        status=status if status != "all" else None,
        event_ticker=event_ticker,
        limit=limit,
    )


@plugin_tool(name="kalshi_get_market")
def get_market(ticker: str) -> dict:
    """Get details for a specific Kalshi market.

    Args:
        ticker: Market ticker (e.g., KXBTC-24DEC31-99999)
    """
    return _client().get_market(ticker)


@plugin_tool(name="kalshi_search_markets")
def search_markets(query: str, limit: int = 20) -> list[dict]:
    """Search Kalshi markets by title.

    Args:
        query: Search query
        limit: Max results
    """
    data = _client().list_markets(status="open", limit=500)
    markets = data.get("markets", [])
    query_lower = query.lower()
    return [
        m
        for m in markets
        if query_lower in m.get("title", "").lower()
        or query_lower in m.get("ticker", "").lower()
        or query_lower in m.get("subtitle", "").lower()
    ][:limit]


@plugin_tool(name="kalshi_list_events")
def list_events(status: str = "open", limit: int = 20) -> dict:
    """List Kalshi event categories.

    Args:
        status: Filter by status (open, closed, settled)
        limit: Max results
    """
    return _client().list_events(
        status=status if status != "all" else None,
        limit=limit,
    )


@plugin_tool(name="kalshi_get_trades")
def get_trades(ticker: str, limit: int = 20) -> dict:
    """Get recent trades for a Kalshi market.

    Args:
        ticker: Market ticker
        limit: Max results
    """
    return _client().get_trades(ticker=ticker, limit=limit)
