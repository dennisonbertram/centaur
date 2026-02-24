"""Messari plugin tools — works both as imported plugin and standalone."""

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

from . import client


def _ensure_key() -> None:
    """Set MESSARI_API_KEY env var from secret() so the client module picks it up."""
    key = secret("MESSARI_API_KEY", default=None)
    if key:
        os.environ.setdefault("MESSARI_API_KEY", key)


@plugin_tool()
async def list_assets(limit: int = 20) -> list[dict]:
    """List crypto assets with basic info and price.

    Args:
        limit: Max number of assets to return
    """
    _ensure_key()
    return client.list_assets(limit=limit)


@plugin_tool()
async def get_asset(asset_key: str) -> dict:
    """Get details for a specific crypto asset.

    Args:
        asset_key: Asset slug or ID (e.g., "bitcoin", "ethereum")
    """
    _ensure_key()
    return client.get_asset(asset_key)


@plugin_tool()
async def get_asset_metrics(asset_key: str) -> dict:
    """Get metrics for an asset (price, volume, market cap, etc).

    Args:
        asset_key: Asset slug or ID
    """
    _ensure_key()
    return client.get_asset_metrics(asset_key)


@plugin_tool()
async def get_asset_profile(asset_key: str) -> dict:
    """Get asset profile (description, links, team, etc).

    Args:
        asset_key: Asset slug or ID
    """
    _ensure_key()
    return client.get_asset_profile(asset_key)


@plugin_tool()
async def get_asset_markets(asset_key: str, limit: int = 20) -> list[dict]:
    """Get markets for an asset.

    Args:
        asset_key: Asset slug or ID
        limit: Max number of markets to return
    """
    _ensure_key()
    return client.get_asset_markets(asset_key)[:limit]


@plugin_tool()
async def get_news(limit: int = 10) -> list[dict]:
    """Get latest crypto news from Messari.

    Args:
        limit: Max number of articles to return
    """
    _ensure_key()
    return client.get_news(limit=limit)


@plugin_tool()
async def get_timeseries(
    asset_key: str,
    metric: str,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Get historical timeseries data for an asset metric.

    Args:
        asset_key: Asset slug or ID
        metric: Metric key (e.g., "price", "mcap", "vol")
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
    """
    _ensure_key()
    return client.get_timeseries(asset_key, metric, start=start, end=end)
