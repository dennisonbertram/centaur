"""Polymarket plugin tools — works both as imported plugin and standalone."""
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

from .client import PolymarketClient


def _client() -> PolymarketClient:
    return PolymarketClient()


@plugin_tool(name="polymarket_list_markets")
def list_markets(limit: int = 20, closed: bool = False) -> list[dict]:
    """List active Polymarket prediction markets sorted by volume.

    Args:
        limit: Max results
        closed: Include closed markets
    """
    return _client().list_markets(limit=limit, closed=closed)


@plugin_tool(name="polymarket_get_market")
def get_market(market_id: str) -> dict:
    """Get details for a specific Polymarket market.

    Args:
        market_id: Market ID or slug
    """
    return _client().get_market(market_id)


@plugin_tool(name="polymarket_search")
def search(query: str, limit: int = 20, closed: bool = False) -> dict:
    """Search Polymarket markets by keyword.

    Args:
        query: Search query
        limit: Max results per type
        closed: Include closed markets
    """
    return _client().search(query, limit=limit, closed=closed)


@plugin_tool(name="polymarket_trending")
def trending(limit: int = 20) -> list[dict]:
    """Get trending Polymarket markets by 24h volume.

    Args:
        limit: Max results
    """
    data = _client().list_markets(limit=limit, closed=False, order="volume24hr", ascending=False)
    return sorted(data, key=lambda x: x.get("volume24hr") or 0, reverse=True)


@plugin_tool(name="polymarket_price")
def price(token_id: str) -> dict:
    """Get current price for a Polymarket token.

    Args:
        token_id: CLOB token ID
    """
    return _client().get_price(token_id)


@plugin_tool(name="polymarket_orderbook")
def orderbook(token_id: str) -> dict:
    """Get orderbook for a Polymarket token.

    Args:
        token_id: CLOB token ID
    """
    return _client().get_book(token_id)
