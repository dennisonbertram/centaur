"""Coin Metrics plugin tools — works both as imported plugin and standalone."""

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

from .client import CoinMetricsClient


def _client() -> CoinMetricsClient:
    return CoinMetricsClient(api_key=secret("COINMETRICS_API_KEY"))


@plugin_tool()
async def list_assets() -> list[dict]:
    """List available assets on Coin Metrics."""
    client = _client()
    try:
        return client.list_assets()
    finally:
        client.close()


@plugin_tool()
async def list_metrics() -> list[dict]:
    """List available metrics on Coin Metrics."""
    client = _client()
    try:
        return client.list_metrics()
    finally:
        client.close()


@plugin_tool()
async def list_exchanges() -> list[dict]:
    """List available exchanges on Coin Metrics."""
    client = _client()
    try:
        return client.list_exchanges()
    finally:
        client.close()


@plugin_tool()
async def get_asset_metrics(
    assets: str,
    metrics: str,
    frequency: str = "1d",
    start_time: str | None = None,
    end_time: str | None = None,
    page_size: int = 1000,
) -> list[dict]:
    """Get timeseries data for asset metrics.

    Args:
        assets: Comma-separated list of assets (e.g., "btc,eth")
        metrics: Comma-separated list of metrics (e.g., "PriceUSD,AdrActCnt")
        frequency: Frequency (1b, 1s, 1m, 5m, 10m, 1h, 1d)
        start_time: Start time in ISO8601 format
        end_time: End time in ISO8601 format
        page_size: Number of results per page
    """
    client = _client()
    try:
        return client.get_asset_metrics(
            assets=assets,
            metrics=metrics,
            frequency=frequency,
            start_time=start_time,
            end_time=end_time,
            page_size=page_size,
        )
    finally:
        client.close()


@plugin_tool()
async def get_market_candles(
    markets: str,
    frequency: str = "1h",
    start_time: str | None = None,
    end_time: str | None = None,
    page_size: int = 1000,
) -> list[dict]:
    """Get market candles (OHLCV).

    Args:
        markets: Comma-separated list of markets (e.g., "coinbase-btc-usd-spot")
        frequency: Candle frequency (1m, 5m, 10m, 15m, 30m, 1h, 4h, 1d)
        start_time: Start time in ISO8601 format
        end_time: End time in ISO8601 format
        page_size: Number of results per page
    """
    client = _client()
    try:
        return client.get_market_candles(
            markets=markets,
            frequency=frequency,
            start_time=start_time,
            end_time=end_time,
            page_size=page_size,
        )
    finally:
        client.close()


@plugin_tool()
async def get_market_trades(
    markets: str,
    start_time: str | None = None,
    end_time: str | None = None,
    page_size: int = 1000,
) -> list[dict]:
    """Get market trades.

    Args:
        markets: Comma-separated list of markets
        start_time: Start time in ISO8601 format
        end_time: End time in ISO8601 format
        page_size: Number of results per page
    """
    client = _client()
    try:
        return client.get_market_trades(
            markets=markets,
            start_time=start_time,
            end_time=end_time,
            page_size=page_size,
        )
    finally:
        client.close()
